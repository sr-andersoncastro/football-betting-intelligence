import { evaluate } from '/lib.mjs';
const $ = id => document.getElementById(id);
let rows = [], selected = [];
const text = (tag, value, className) => { const node=document.createElement(tag); node.textContent=value; if(className) node.className=className; return node; };
function metric(parent,label,value){const card=text('div','','metric');card.append(text('span',label),text('strong',value));parent.append(card);}
function render(){
  selected=rows.filter(r=>(!$('competition').value || r.competition===$('competition').value) && (!$('status').value || r.status===$('status').value) && (r.home+' '+r.away).toLocaleLowerCase('pt-BR').includes($('search').value.trim().toLocaleLowerCase('pt-BR')));
  const finished=selected.filter(r=>r.status==='finished');
  $('metrics').replaceChildren();
  metric($('metrics'),'Partidas na seleção',selected.length);
  metric($('metrics'),'Partidas encerradas',finished.length);
  metric($('metrics'),'Média de gols',finished.length?(finished.reduce((s,r)=>s+r.homeGoals+r.awayGoals,0)/finished.length).toFixed(2):'—');
  $('count').textContent=selected.length+' partida(s) · dados fictícios';
  $('fixtures').replaceChildren();
  for(const r of selected){
    const card=text('article','','fixture'), detail=text('div','');
    detail.append(text('p',r.competition.toLocaleUpperCase('pt-BR')),text('h3',r.home+' × '+r.away),text('p',new Intl.DateTimeFormat('pt-BR',{dateStyle:'medium',timeStyle:'short',timeZone:'America/Sao_Paulo'}).format(new Date(r.kickoff))+' · Brasília'));
    const score=text('div',r.status==='finished'?r.homeGoals+' : '+r.awayGoals:'Agendada','result');
    if(r.status==='finished') score.append(text('small',r.corners+' escanteios · '+r.cards+' cartões'));
    if(r.prediction) detail.append(text('p','Previsão sintética 1 / X / 2: '+r.prediction.probabilities.map(p=>(100*p).toFixed(0)+'%').join(' / ')),text('p','Modelo '+r.prediction.version+' · Registro '+new Date(r.prediction.createdAt).toISOString()));
    card.append(detail,score);$('fixtures').append(card);
  }
  if(!selected.length)$('fixtures').append(text('p','Nenhuma partida corresponde aos filtros.','empty'));
  const scores=evaluate(selected);$('scores').replaceChildren();
  metric($('scores'),'Previsões avaliadas',scores.count);
  metric($('scores'),'Brier Score',scores.brier?.toFixed(3)??'—');
  metric($('scores'),'Log loss',scores.logLoss?.toFixed(3)??'—');
}
for(const id of ['competition','status','search']) $(id).addEventListener('input',render);
$('export').addEventListener('click',()=>{
  const safe=value=>'"'+String(value??'').replace(/^[=+@\-]/,"'").replaceAll('"','""')+'"';
  const fields=['id','competition','home','away','kickoff','status','homeGoals','awayGoals','corners','cards'];
  const csv='\uFEFF'+[fields.join(','),...selected.map(r=>fields.map(k=>safe(r[k])).join(','))].join('\r\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download='partidas-demonstrativas.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
try{
 const response=await fetch('/api/v1/fixtures');if(!response.ok)throw new Error('Falha na consulta');
 rows=(await response.json()).fixtures;
 for(const c of [...new Set(rows.map(r=>r.competition))].sort()) {const option=text('option',c);option.value=c;$('competition').append(option);}
 render();
}catch{ $('fixtures').textContent='Não foi possível carregar os dados. Recarregue a página para tentar novamente.';$('export').disabled=true; }
