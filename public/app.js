import {evaluate} from '/lib.mjs';
import {standings} from '/analytics.mjs';
const $=id=>document.getElementById(id);
let rows=[],selected=[],mode='real',visible=50,installation;
let predictionGeneration=0;const predictionRequests=new Set();
const formatter=new Intl.DateTimeFormat('pt-BR',{dateStyle:'medium',timeStyle:'short',timeZone:'America/Sao_Paulo'});
const date=value=>formatter.format(new Date(value));
const day=value=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
const today=()=>day(new Date());
const offsetDay=n=>{const d=new Date(today()+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+n);return day(d);};
const text=(tag,value,className)=>{const node=document.createElement(tag);node.textContent=value;if(className)node.className=className;return node;};
const statuses={scheduled:'Agendada',finished:'Encerrada',live:'Em andamento na coleta',postponed:'Adiada',cancelled:'Cancelada',suspended:'Suspensa'};
function metric(parent,label,value){const card=text('div','','metric');card.append(text('span',label),text('strong',value));parent.append(card);}
function competitionFixtures(){return rows.filter(r=>(!$('competition').value||r.competition===$('competition').value)&&(!$('season').value||String(r.season)===$('season').value));}
function seasons(){
  const previous=$('season').value;
  $('season').replaceChildren(new Option('Todas as temporadas',''));
  const matching=rows.filter(r=>!$('competition').value||r.competition===$('competition').value);
  for(const season of [...new Set(matching.map(r=>r.season).filter(Boolean))].sort((a,b)=>b-a)){
    const label=$('competition').value?matching.find(r=>r.season===season).seasonLabel??`${season}/${season+1}`:String(season);
    $('season').append(new Option(label,String(season)));
  }
  if([...$('season').options].some(o=>o.value===previous))$('season').value=previous;
}
function renderStandings(){
  $('standings').replaceChildren();
  for(const group of standings(competitionFixtures())){
    const table=text('table',''),caption=text('caption',group.competition+' · '+group.seasonLabel+' · '+group.matches+' partidas encerradas');table.append(caption);
    const head=text('thead',''),header=text('tr','');
    for(const label of ['#','Equipe','Pts','J','V','E','D','GP','GC','SG','Aprov.']){const cell=text('th',label);cell.scope='col';header.append(cell);}
    head.append(header);table.append(head);const body=text('tbody','');
    group.teams.forEach((team,index)=>{const row=text('tr','');for(const value of [index+1,team.name,team.points,team.played,team.won,team.drawn,team.lost,team.goalsFor,team.goalsAgainst,team.goalDifference,team.pointsPercentage.toFixed(1)+'%'])row.append(text('td',value));body.append(row);});
    table.append(body);const wrapper=text('div','','table-scroll');wrapper.tabIndex=0;wrapper.setAttribute('role','region');wrapper.setAttribute('aria-label',caption.textContent);wrapper.append(table);$('standings').append(wrapper);
  }
  if(!$('standings').children.length)$('standings').append(text('p','Sem classificação de liga nesta seleção. Competições de copa exibem partidas e resultados, sem uma tabela única que misture fases.','empty'));
}
const pilotLeagues=[{code:'bra.1',name:'Brasileirão Série A'},{code:'eng.1',name:'Premier League'},{code:'esp.1',name:'La Liga'},{code:'bl1',name:'Bundesliga'}];
function fold(label,className){const details=text('details','',className),summary=text('summary',label);details.append(summary);return {details,summary};}
function renderLeagueReport(report,body){
  body.replaceChildren();
  body.append(text('p',`${report.trainingMatches} partidas no treino · Coleta: ${report.latestDataAt?date(report.latestDataAt):'indisponível'}${report.dataStale?' · coleta defasada: previsões suspensas':''}.`,'muted'));
  const groups=new Map();
  for(const match of [...report.forecasts].sort((a,b)=>Date.parse(a.kickoff)-Date.parse(b.kickoff))){const key=day(match.kickoff);if(!groups.has(key))groups.set(key,[]);groups.get(key).push(match);}
  for(const [key,matches] of groups){
    const label=new Intl.DateTimeFormat('pt-BR',{weekday:'long',day:'2-digit',month:'long',timeZone:'America/Sao_Paulo'}).format(new Date(matches[0].kickoff));
    const group=fold((key===today()?'Hoje · ':'')+label+' · '+matches.length+' jogo(s)','prediction-day');
    for(const f of matches){
      const time=new Intl.DateTimeFormat('pt-BR',{hour:'2-digit',minute:'2-digit',timeZone:'America/Sao_Paulo'}).format(new Date(f.kickoff));
      const match=fold(time+' · '+f.home+' × '+f.away,'prediction-match');
      const chances=text('div','','probability-grid');
      [f.home,'Empate',f.away].forEach((label,i)=>{const cell=text('div','','probability-cell');cell.append(text('span',label),text('strong',(100*f.probabilities[i]).toFixed(1)+'%'));chances.append(cell);});
      match.details.append(chances);
      const explanation=fold('Ver análise e registro','prediction-explanation'),h=f.evidence.home,a=f.evidence.away;
      explanation.details.append(text('p',`Forma recente suavizada: ${f.home}, ${h.lastTen.points.toFixed(2)} pontos/jogo; ${f.away}, ${a.lastTen.points.toFixed(2)}. No mando desta partida: ${h.venueLastTen.points.toFixed(2)} em casa e ${a.venueLastTen.points.toFixed(2)} fora.`),text('p','Registro: '+date(f.createdAt)+' · Histórico anterior a '+date(f.trainingCutoff)+' · Modelo '+f.version,'muted'));
      match.details.append(explanation.details);group.details.append(match.details);
    }
    body.append(group.details);
  }
  if(!report.forecasts.length)body.append(text('p','Sem probabilidades disponíveis para os próximos 7 dias. A partida precisa estar agendada, ter horário confirmado, coleta recente e histórico suficiente.','empty'));
  const p=report.prospectiveEvaluation,w=report.walkForward,validation=fold('Ver avaliação deste campeonato','prediction-validation');
  validation.details.append(text('p',w.model.count?`Teste histórico temporal: ${w.model.count} jogos. Acerto do resultado mais provável: ${(100*w.model.accuracy).toFixed(1)}%; referência simples: ${(100*w.baseline.accuracy).toFixed(1)}%. ${w.model.accuracy>w.baseline.accuracy?'A diferença observada não garante melhora futura.':'Maior taxa de acerto ainda não foi demonstrada nesta amostra.'} Simulação retrospectiva com dados corrigidos pela fonte.`:'Histórico insuficiente para avaliar o modelo.'));
  const scores=text('div','','metrics');metric(scores,'Brier do modelo',w.model.brier?.toFixed(3)??'—');metric(scores,'Brier da referência',w.baseline.brier?.toFixed(3)??'—');metric(scores,'Previsões futuras já avaliadas',p?.count??0);validation.details.append(scores);
  validation.details.append(text('p',(p?.count?`Registros preservados antes do início: ${p.count} jogos; acerto ${(100*p.accuracy).toFixed(1)}%, Brier ${p.brier.toFixed(3)}.`:'A avaliação prospectiva começará após o término dos jogos com previsões registradas.')+' '+report.storage,'muted'));
  body.append(validation.details);
}
function renderModel(){
  predictionGeneration++;for(const request of predictionRequests)request.abort();predictionRequests.clear();
  const generation=predictionGeneration;$('predictions').replaceChildren();
  $('model-notice').textContent=mode==='demo'?'Probabilidades disponíveis somente com dados reais.':'Abra um campeonato, escolha a data e depois a partida. Horários de Brasília.';
  if(mode==='demo')return;
  for(const league of pilotLeagues){
    const group=fold(league.name,'prediction-league'),body=text('div','','prediction-league-body'),hint=text('span','Abrir jogos','fold-hint');group.summary.append(hint);group.details.append(body);$('predictions').append(group.details);
    let loaded=false,loading=false;
    async function loadLeague(){
      if(loaded||loading||generation!==predictionGeneration)return;
      loading=true;body.replaceChildren(text('p','Carregando jogos e probabilidades…','muted'));
      const request=new AbortController();predictionRequests.add(request);
      try{
        const response=await fetch('/api/v1/predictions?competition='+encodeURIComponent(league.code),{signal:request.signal});
        if(!response.ok)throw new Error('Falha na consulta');const report=await response.json();
        if(generation!==predictionGeneration)return;
        if(!report.walkForward)throw new Error('Modelo indisponível');
        renderLeagueReport(report,body);hint.textContent=report.forecasts.length+' jogo(s)';loaded=true;
      }catch(error){
        if(error.name==='AbortError'||generation!==predictionGeneration)return;
        body.replaceChildren(text('p','Não foi possível carregar este campeonato.','muted'));
        const retry=text('button','Tentar novamente');retry.type='button';retry.addEventListener('click',loadLeague);body.append(retry);
      }finally{loading=false;predictionRequests.delete(request);}
    }
    group.details.addEventListener('toggle',()=>{if(group.details.open)void loadLeague();});
  }
}
function render(){
  const period=$('period').value;
  selected=competitionFixtures().filter(r=>{
    const d=day(r.kickoff);
    return (!$('status').value||r.status===$('status').value)&&(r.home+' '+r.away).toLocaleLowerCase('pt-BR').includes($('search').value.trim().toLocaleLowerCase('pt-BR'))&&
      (period==='all'||period==='today'&&d===today()||period==='next'&&d>=today()&&d<=offsetDay(7)||period==='recent'&&d>=offsetDay(-7)&&d<=today());
  }).sort((a,b)=>period==='recent'?Date.parse(b.kickoff)-Date.parse(a.kickoff):Date.parse(a.kickoff)-Date.parse(b.kickoff));
  const finished=selected.filter(r=>r.status==='finished');$('metrics').replaceChildren();
  metric($('metrics'),'Partidas na seleção',selected.length);metric($('metrics'),'Partidas encerradas',finished.length);
  metric($('metrics'),'Média de gols',finished.length?(finished.reduce((s,r)=>s+r.homeGoals+r.awayGoals,0)/finished.length).toFixed(2):'—');
  $('count').textContent=selected.length+' partida(s) · '+(mode==='demo'?'dados fictícios':[...new Set(selected.map(r=>r.source))].join(' + '))+' · mostrando '+Math.min(visible,selected.length);
  $('fixtures').replaceChildren();
  for(const r of selected.slice(0,visible)){
    const card=text('article','','fixture'),detail=text('div','');
    detail.append(text('p',r.competition.toLocaleUpperCase('pt-BR')),text('h3',r.home+' × '+r.away),text('p',date(r.kickoff)+' · Brasília'+(r.kickoffConfirmed===false?' · horário a confirmar':'')));
    const score=text('div',r.status==='finished'?r.homeGoals+' : '+r.awayGoals:statuses[r.status],'result');
    if(r.status==='finished')score.append(text('small','Resultado final'));
    if(r.venue)detail.append(text('p',r.venue));
    if(r.source)detail.append(text('p',r.source+' · temporada '+(r.seasonLabel??`${r.season}/${r.season+1}`)+' · coleta '+date(r.collectedAt)));
    if(r.prediction)detail.append(text('p','Previsão sintética 1 / X / 2: '+r.prediction.probabilities.map(p=>(100*p).toFixed(0)+'%').join(' / ')));
    card.append(detail,score);$('fixtures').append(card);
  }
  if(!selected.length)$('fixtures').append(text('p','Nenhuma partida neste período. Selecione “Todas as datas” ou outro campeonato.','empty'));
  $('more').hidden=visible>=selected.length;$('export').disabled=!selected.length;
  const scores=evaluate(selected);$('scores').replaceChildren();metric($('scores'),'Previsões avaliadas',scores.count);metric($('scores'),'Brier Score',scores.brier?.toFixed(3)??'—');metric($('scores'),'Log loss',scores.logLoss?.toFixed(3)??'—');renderStandings();
}
$('competition').addEventListener('input',()=>{seasons();visible=50;render();});
for(const id of ['season','status','search','period'])$(id).addEventListener('input',()=>{visible=50;render();});
$('more').addEventListener('click',()=>{visible+=50;render();});
$('export').addEventListener('click',()=>{
  const safe=value=>'"'+String(value??'').replace(/^(\s*[=+@\-])/u,"'$1").replaceAll('"','""')+'"';
  const fields=['id','competition','season','seasonLabel','home','away','kickoff','kickoffConfirmed','status','homeGoals','awayGoals','source','collectedAt'];
  const csv='\uFEFF'+[fields.join(','),...selected.map(r=>fields.map(k=>safe(r[k])).join(','))].join('\r\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=mode==='demo'?'partidas-demonstrativas.csv':'football-intelligence.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
async function load(){
 $('refresh').disabled=true;
 try{
  const [response,statusResponse]=await Promise.all([fetch('/api/v1/fixtures'),fetch('/api/v1/data-status')]);if(!response.ok||!statusResponse.ok)throw new Error('Falha na consulta');
  const status=await statusResponse.json();mode=status.mode;rows=(await response.json()).fixtures;
  renderModel();
  $('mode').textContent=mode==='demo'?'● DEMONSTRAÇÃO':'● DADOS REAIS';
  $('notice').textContent=mode==='demo'?'Modo de testes: dados fictícios.':`OpenLigaDB + ESPN · Última coleta: ${status.latestCollectedAt?date(status.latestCollectedAt)+' (Brasília)':'indisponível'}. ${status.stale?'Há competições sem coleta recente; consulte a cobertura abaixo.':'Dados coletados periodicamente; não é um placar ao vivo.'}`;
  if(mode==='demo')$('evaluation-note').textContent='Previsões sintéticas para testes. Não representam um modelo treinado.';
  $('storage').textContent=status.storage;$('coverage-list').replaceChildren();$('captures').replaceChildren();
  for(const item of status.coverage)$('coverage-list').append(text('p',item.name+' — '+(item.status==='available'?'integrado · '+item.source+(item.stale?' · coleta defasada':'')+' · anos consultados: '+item.calendarYears.join(', '):'aguardando dados')));
  for(const capture of status.captures){const el=text('div','','capture');el.append(text('strong',capture.scope??capture.source),text('p','Coletado em '+date(capture.collectedAt)+' · Brasília'),text('code','SHA-256: '+capture.sha256));$('captures').append(el);}
  const previous=$('competition').value;
  $('competition').replaceChildren(new Option('Todos os campeonatos',''));
  for(const c of [...new Set(rows.map(r=>r.competition))].sort())$('competition').append(new Option(c,c));
  $('competition').value=[...$('competition').options].some(o=>o.value===previous)&&previous?previous:rows.some(r=>r.competition==='Brasileirão Série A')?'Brasileirão Série A':'';
  seasons();visible=50;render();
 }catch{predictionGeneration++;for(const request of predictionRequests)request.abort();predictionRequests.clear(); $('notice').textContent='Sem conexão com os dados. Os resultados não estão disponíveis offline.';$('mode').textContent='● SEM CONEXÃO';rows=[];selected=[];$('metrics').replaceChildren();$('scores').replaceChildren();$('standings').replaceChildren();$('predictions').replaceChildren();$('model-notice').textContent='Probabilidades indisponíveis sem conexão.';$('fixtures').textContent='Não foi possível carregar as partidas. Toque em Atualizar para tentar novamente.';$('export').disabled=true;$('more').hidden=true;}
 finally{$('refresh').disabled=false;}
}
$('refresh').addEventListener('click',load);
window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();installation=event;$('install').hidden=false;});
$('install').addEventListener('click',async()=>{if(installation){await installation.prompt();await installation.userChoice;installation=null;$('install').hidden=true;}});
window.addEventListener('appinstalled',()=>{$('install').hidden=true;});
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
await load();
