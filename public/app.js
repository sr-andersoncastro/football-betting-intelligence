import { evaluate } from '/lib.mjs';
const $ = id => document.getElementById(id);
let rows = [], selected = [], mode='real', visible=50;
const date=value=>new Intl.DateTimeFormat('pt-BR',{dateStyle:'medium',timeStyle:'short',timeZone:'America/Sao_Paulo'}).format(new Date(value));
const text = (tag, value, className) => { const node=document.createElement(tag); node.textContent=value; if(className) node.className=className; return node; };
function metric(parent,label,value){const card=text('div','','metric');card.append(text('span',label),text('strong',value));parent.append(card);}
function render(){
  selected=rows.filter(r=>(!$('competition').value || r.competition===$('competition').value) && (!$('season').value || String(r.season)===$('season').value) && (!$('status').value || r.status===$('status').value) && (r.home+' '+r.away).toLocaleLowerCase('pt-BR').includes($('search').value.trim().toLocaleLowerCase('pt-BR'))).sort((a,b)=>Date.parse(a.kickoff)-Date.parse(b.kickoff));
  const finished=selected.filter(r=>r.status==='finished');
  $('metrics').replaceChildren();
  metric($('metrics'),'Partidas na seleção',selected.length);
  metric($('metrics'),'Partidas encerradas',finished.length);
  metric($('metrics'),'Média de gols',finished.length?(finished.reduce((s,r)=>s+r.homeGoals+r.awayGoals,0)/finished.length).toFixed(2):'—');
  $('count').textContent=selected.length+' partida(s) · '+(mode==='demo'?'dados fictícios':'fonte: OpenLigaDB')+' · mostrando '+Math.min(visible,selected.length);
  $('fixtures').replaceChildren();
  for(const r of selected.slice(0,visible)){
    const card=text('article','','fixture'), detail=text('div','');
    detail.append(text('p',r.competition.toLocaleUpperCase('pt-BR')),text('h3',r.home+' × '+r.away),text('p',new Intl.DateTimeFormat('pt-BR',{dateStyle:'medium',timeStyle:'short',timeZone:'America/Sao_Paulo'}).format(new Date(r.kickoff))+' · Brasília'));
    const score=text('div',r.status==='finished'?r.homeGoals+' : '+r.awayGoals:'Não encerrada','result');
    if(r.status==='finished') score.append(text('small',(r.corners??'—')+' escanteios · '+(r.cards??'—')+' cartões'));
    if(r.source)detail.append(text('p',r.source+' · temporada '+r.season+'/'+(r.season+1)+' · coleta '+date(r.collectedAt)));
    if(r.prediction) detail.append(text('p','Previsão sintética 1 / X / 2: '+r.prediction.probabilities.map(p=>(100*p).toFixed(0)+'%').join(' / ')),text('p','Modelo '+r.prediction.version+' · Registro '+new Date(r.prediction.createdAt).toISOString()));
    card.append(detail,score);$('fixtures').append(card);
  }
  if(!selected.length)$('fixtures').append(text('p','Nenhuma partida corresponde aos filtros.','empty'));
  $('more').hidden=visible>=selected.length;
  const scores=evaluate(selected);$('scores').replaceChildren();
  metric($('scores'),'Previsões avaliadas',scores.count);
  metric($('scores'),'Brier Score',scores.brier?.toFixed(3)??'—');
  metric($('scores'),'Log loss',scores.logLoss?.toFixed(3)??'—');
}
for(const id of ['competition','season','status','search']) $(id).addEventListener('input',()=>{visible=50;render();});
$('more').addEventListener('click',()=>{visible+=50;render();});
$('export').addEventListener('click',()=>{
  const safe=value=>'"'+String(value??'').replace(/^[=+@\-]/,"'").replaceAll('"','""')+'"';
  const fields=['id','competition','season','home','away','kickoff','status','homeGoals','awayGoals','corners','cards','source','collectedAt'];
  const csv='\uFEFF'+[fields.join(','),...selected.map(r=>fields.map(k=>safe(r[k])).join(','))].join('\r\n');
  const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download=mode==='demo'?'partidas-demonstrativas.csv':'partidas-openligadb.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
try{
 const [response,statusResponse]=await Promise.all([fetch('/api/v1/fixtures'),fetch('/api/v1/data-status')]);if(!response.ok || !statusResponse.ok)throw new Error('Falha na consulta');
 const status=await statusResponse.json();mode=status.mode;rows=(await response.json()).fixtures;
 $('mode').textContent=mode==='demo'?'● DEMONSTRAÇÃO':'● DADOS REAIS';
 $('notice').textContent=mode==='demo'?'Modo de testes: todos os dados são fictícios.':`Fonte: OpenLigaDB · Última coleta: ${status.latestCollectedAt?date(status.latestCollectedAt)+' (Brasília)':'indisponível'}. ${status.stale?'A captura tem mais de 24 horas; consulte os resultados com cautela.':'Atualização periódica; não é um serviço ao vivo.'}`;
 if(mode==='demo')$('evaluation-note').textContent='Previsões sintéticas para testes. Não representam um modelo treinado.';
 $('storage').textContent=status.storage;
 for(const item of status.coverage)$('coverage-list').append(text('p',item.name+' — '+(item.status==='available'?'dados integrados':'integração pendente')));
 for(const capture of status.captures){const el=text('div','','capture');el.append(text('strong',capture.source+' · '+capture.season+'/'+(capture.season+1)),text('p','Coletado em '+date(capture.collectedAt)+' · Brasília'),text('code','SHA-256: '+capture.sha256));$('captures').append(el);}
 for(const season of [...new Set(rows.map(r=>r.season).filter(Boolean))].sort((a,b)=>b-a)){const option=text('option',season+'/'+(season+1));option.value=String(season);$('season').append(option);}
 if($('season').options.length>1)$('season').selectedIndex=1;
 for(const c of [...new Set(rows.map(r=>r.competition))].sort()) {const option=text('option',c);option.value=c;$('competition').append(option);}
 render();
}catch{ $('fixtures').textContent='Não foi possível carregar os dados. Recarregue a página para tentar novamente.';$('export').disabled=true; }
