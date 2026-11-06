// Lightweight binary learning models; no LLM, external API, or betting execution.
export const MARKET_GROUPS=[{code:'goals',name:'Gols',version:'goals-binary-v1',thresholds:[1.5,2.5,3.5],scale:6},{code:'corners',name:'Escanteios',version:'corners-binary-v1',thresholds:[8.5,9.5,10.5],scale:20},{code:'fouls',name:'Faltas',version:'fouls-binary-v1',thresholds:[24.5,29.5,34.5],scale:60}];
const teamId=(r,side)=>String(r[side+'TeamId']??r[side]);
const sigmoid=z=>1/(1+Math.exp(-Math.max(-30,Math.min(30,z))));
const dot=(w,x)=>w.reduce((sum,v,i)=>sum+v*x[i],0);
function counts(row,group){
 const names=group.code==='goals'?['homeGoals','awayGoals']:group.code==='corners'?['homeCorners','awayCorners']:['homeFouls','awayFouls'];
 const values=names.map(n=>row[n]);return values.every(v=>Number.isInteger(v)&&v>=0)?values:null;
}
function definitions(group){return [...group.thresholds.map(t=>({id:group.code+'-over-'+t,label:'Mais de '+String(t).replace('.',',')+' '+(group.code==='goals'?'gols':group.code==='corners'?'escanteios':'faltas'),threshold:t})),...(group.code==='goals'?[{id:'both-teams-score',label:'Ambas as equipes marcam',both:true}]:[])];}
const observed=(values,def)=>def.both?Number(values[0]>0&&values[1]>0):Number(values[0]+values[1]>def.threshold);
function create(group){return {group,teams:new Map(),history:[],heads:definitions(group).map(def=>({def,weights:Array(5).fill(0),yes:1,no:1,records:[]}))};}
function team(state,id){if(!state.teams.has(id))state.teams.set(id,[]);return state.teams.get(id);}
function average(rows,field,prior){let sum=4*prior,weight=4;rows.slice(-10).reverse().forEach((r,i)=>{const w=.85**i;sum+=w*r[field];weight+=w;});return sum/weight;}
function inputs(state,row){
 const h=team(state,teamId(row,'home')),a=team(state,teamId(row,'away'));
 const prior=state.history.length?state.history.reduce((s,r)=>s+r[0]+r[1],0)/(2*state.history.length):state.group.scale/4;
 const hf=average(h,'for',prior),ha=average(h,'against',prior),af=average(a,'for',prior),aa=average(a,'against',prior);
 const hv=h.filter(r=>r.home),av=a.filter(r=>!r.home);
 return {x:[1,(hf+aa)/state.group.scale,(af+ha)/state.group.scale,(average(hv,'for',prior)+average(av,'for',prior))/state.group.scale,Math.abs(hf-af)/state.group.scale],ready:state.history.length>=160&&h.length>=8&&a.length>=8,evidence:{homeMatches:h.length,awayMatches:a.length}};
}
function score(records,field){if(!records.length)return {count:0,brier:null,logLoss:null};let brier=0,loss=0;for(const r of records){const p=r[field];brier+=(p-r.actual)**2;loss-=r.actual*Math.log(Math.max(1e-15,p))+(1-r.actual)*Math.log(Math.max(1e-15,1-p));}return {count:records.length,brier:brier/records.length,logLoss:loss/records.length};}
function monotone(heads,values){
 // Projection onto decreasing probabilities for nested totals (P>3.5 <= P>2.5).
 const indexes=heads.map((h,i)=>h.def.both?-1:i).filter(i=>i>=0),blocks=[];
 for(const i of indexes){blocks.push({indexes:[i],sum:values[i],count:1});while(blocks.length>1){const a=blocks.at(-2),b=blocks.at(-1);if(a.sum/a.count>=b.sum/b.count)break;blocks.splice(-2,2,{indexes:[...a.indexes,...b.indexes],sum:a.sum+b.sum,count:a.count+b.count});}}
 const projected=[...values];for(const b of blocks)for(const i of b.indexes)projected[i]=b.sum/b.count;return projected;
}
function predict(state,x){return monotone(state.heads,state.heads.map(h=>sigmoid(dot(h.weights,x))));}
function observe(state,row,f){
 const values=counts(row,state.group);if(!values)return;
 for(const h of state.heads){const y=observed(values,h.def),p=sigmoid(dot(h.weights,f.x));for(let j=0;j<f.x.length;j++)h.weights[j]-=.03*((p-y)*f.x[j]+(j===0?0:.003*h.weights[j]));h.yes+=y;h.no+=1-y;}
 state.history.push(values);team(state,teamId(row,'home')).push({for:values[0],against:values[1],home:true});team(state,teamId(row,'away')).push({for:values[1],against:values[0],home:false});
}
export function buildMarkets(fixtures,now,competitionCode,upcoming){
 const cutoff=now.toISOString().slice(0,10)+'T00:00:00.000Z';
 const rows=fixtures.filter(r=>r.competitionCode===competitionCode&&r.status==='finished'&&Date.parse(r.kickoff)+6*3600000<Date.parse(cutoff)).sort((a,b)=>Date.parse(a.kickoff)-Date.parse(b.kickoff)||a.id.localeCompare(b.id));
 const predictions=new Map(upcoming.map(r=>[r.id,[]])),evaluation=[];
 for(const group of MARKET_GROUPS){
  const state=create(group);let pending=[];
  for(let i=0;i<rows.length;){
   const day=rows[i].kickoff.slice(0,10),dayStart=Date.parse(day+'T00:00:00Z');
   const ready=pending.filter(p=>Date.parse(p.row.kickoff)+6*3600000<dayStart);pending=pending.filter(p=>Date.parse(p.row.kickoff)+6*3600000>=dayStart);
   for(const p of ready)observe(state,p.row,p.f);
   while(i<rows.length&&rows[i].kickoff.slice(0,10)===day){const row=rows[i++];if(!counts(row,group))continue;const f=inputs(state,row),probabilities=predict(state,f.x),values=counts(row,group);if(f.ready)state.heads.forEach((h,index)=>h.records.push({fixtureId:row.id,kickoff:row.kickoff,probability:probabilities[index],baseline:h.yes/(h.yes+h.no),actual:observed(values,h.def)}));pending.push({row,f});}
  }
  for(const p of pending)observe(state,p.row,p.f);
  for(const row of upcoming){const f=inputs(state,row),values=predict(state,f.x);predictions.get(row.id).push({code:group.code,name:group.name,version:group.version,status:f.ready?'experimental':'unavailable',reason:f.ready?null:'Histórico insuficiente: exige 160 partidas com a estatística e 8 por equipe.',trainingMatches:state.history.length,evidence:f.evidence,markets:f.ready?state.heads.map((h,i)=>({id:h.def.id,label:h.def.label,threshold:h.def.threshold??null,both:h.def.both??false,probability:values[i],oppositeProbability:1-values[i]})):[]});}
  evaluation.push({code:group.code,name:group.name,version:group.version,trainingMatches:state.history.length,markets:state.heads.map(h=>({id:h.def.id,label:h.def.label,model:score(h.records,'probability'),baseline:score(h.records,'baseline')}))});
 }
 return {predictions,evaluation,signature:MARKET_GROUPS.map(g=>g.version).join('|')};
}
export function evaluateRecordedMarkets(predictions,fixtures,now,competitionCode){
 const finished=new Map(fixtures.filter(r=>r.competitionCode===competitionCode&&r.status==='finished'&&Date.parse(r.kickoff)<now.getTime()).map(r=>[r.id,r]));
 return MARKET_GROUPS.map(group=>({code:group.code,name:group.name,markets:definitions(group).map(def=>{
  const latest=new Map();for(const p of predictions){const row=finished.get(p.fixtureId),g=p.extraMarkets?.find(g=>g.code===group.code&&g.version===group.version),market=g?.markets.find(m=>m.id===def.id);if(!row||!market||p.kickoff!==row.kickoff||Date.parse(p.createdAt)>=Date.parse(row.kickoff)||!counts(row,group))continue;if(!latest.has(row.id)||Date.parse(latest.get(row.id).p.createdAt)<Date.parse(p.createdAt))latest.set(row.id,{p,market,row});}
  return {id:def.id,label:def.label,...score([...latest.values()].map(({market,row})=>({probability:market.probability,actual:observed(counts(row,group),def)})),'probability')};
 })}));
}

export function validateExtraMarkets(groups){
 if(!Array.isArray(groups))throw new Error('Mercados adicionais inválidos');
 for(const g of groups){const def=MARKET_GROUPS.find(d=>d.code===g.code&&d.version===g.version);if(!def||!Array.isArray(g.markets))throw new Error('Versão do mercado inválida');
 for(const m of g.markets)if(!definitions(def).some(d=>d.id===m.id)||!Number.isFinite(m.probability)||m.probability<0||m.probability>1||!Number.isFinite(m.oppositeProbability)||Math.abs(m.probability+m.oppositeProbability-1)>1e-8)throw new Error('Probabilidade adicional inválida');
 }
}
