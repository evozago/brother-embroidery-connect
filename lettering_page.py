# -*- coding: utf-8 -*-
"""Página web do Gerador de Letreiros (servida por server.py em /letreiro)."""

PAGE = r"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Gerador de Letreiros</title>
<style>
 :root{--bg:#0f1115;--card:#1a1d24;--ln:#2a2f3a;--tx:#e8eaed;--mut:#9aa0ab;--ac:#4f8cff;--ok:#39c07a;--er:#ff5d5d}
 *{box-sizing:border-box}body{margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--tx)}
 .wrap{max-width:1100px;margin:0 auto;padding:20px 16px}
 h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mut);font-size:13px;margin-bottom:16px}
 a{color:var(--ac)}
 .grid{display:grid;grid-template-columns:minmax(300px,420px) 1fr;gap:16px}
 @media(max-width:820px){.grid{grid-template-columns:1fr}}
 .card{background:var(--card);border:1px solid var(--ln);border-radius:14px;padding:16px;margin-bottom:16px}
 h3{margin:0 0 10px;font-size:15px}
 label{display:block;color:var(--mut);font-size:12px;margin:10px 0 4px}
 textarea,input,select{width:100%;background:#11141a;color:var(--tx);border:1px solid var(--ln);border-radius:8px;padding:8px;font-size:15px}
 textarea{min-height:70px;resize:vertical}
 .two{display:grid;grid-template-columns:1fr 1fr;gap:10px}
 .fonts{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px}
 .font{border:1px solid var(--ln);border-radius:10px;padding:8px;cursor:pointer;background:#11141a;text-align:center}
 .font.sel{border-color:var(--ac);box-shadow:0 0 0 2px #4f8cff55}
 .font .s{font-size:28px;line-height:1.2;color:#fff;white-space:nowrap;overflow:hidden}
 .font .n{font-size:11px;color:var(--mut)}
 .rng{display:flex;align-items:center;gap:8px}.rng input[type=range]{flex:1}.rng b{min-width:52px;text-align:right;font-size:13px}
 .sw{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}.sw i{width:24px;height:24px;border-radius:50%;border:2px solid #fff3;cursor:pointer}
 button{background:var(--ac);color:#fff;border:0;border-radius:9px;padding:10px 14px;font-size:14px;font-weight:600;cursor:pointer}
 button.ghost{background:transparent;border:1px solid var(--ln);color:var(--tx)}
 button:disabled{opacity:.5;cursor:default}
 .btns{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
 #pv{background:#f7f5f0;border-radius:10px;min-height:180px;display:flex;align-items:center;justify-content:center;padding:8px}
 #pv svg{max-height:60vh}
 .ficha{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:8px;margin-top:12px}
 .ficha>div{background:#11141a;border:1px solid var(--ln);border-radius:8px;padding:8px}.ficha .k{color:var(--mut);font-size:11px}.ficha .v{font-weight:700}
 .msg{margin-top:10px;font-size:13px}.ok{color:var(--ok)}.er{color:var(--er)}
 .muted{color:var(--mut);font-size:12px}
</style><style id="ff"></style></head><body><div class="wrap">
<h1>✍️ Gerador de Letreiros</h1>
<div class="sub">Digite o texto, escolha fonte, cor e tamanho — o arquivo .pes sai pronto, com base, ponto cheio e costura da esquerda para a direita. <a href="/">← voltar ao painel</a></div>
<div class="grid">
 <div>
  <div class="card">
   <h3>Texto</h3>
   <textarea id="txt" placeholder="Ex.: Felipe">Felipe</textarea>
   <div class="muted">Aperte Enter para quebrar em duas linhas (ex.: nome em cima, sobrenome embaixo).</div>
  </div>
  <div class="card"><h3>Fonte</h3><div class="fonts" id="fonts"></div></div>
  <div class="card">
   <h3>Tamanho</h3>
   <div class="two">
    <div><label>Largura máxima (mm)</label><input id="maxw" type="number" min="5" step="0.5" value="80"></div>
    <div><label>Altura máxima (mm)</label><input id="maxh" type="number" min="5" step="0.5" placeholder="sem limite"></div>
   </div>
   <div class="muted" style="margin-top:6px">O desenho cresce até bater no primeiro limite, sem deformar.</div>
   <label>Esticar na horizontal</label><div class="rng"><input id="sx" type="range" min="50" max="200" value="100"><b id="sxv">100%</b></div>
   <label>Esticar na vertical</label><div class="rng"><input id="sy" type="range" min="50" max="200" value="100"><b id="syv">100%</b></div>
   <label>Espaço extra entre letras</label><div class="rng"><input id="sp" type="range" min="-2" max="6" step="0.1" value="0"><b id="spv">0 mm</b></div>
   <label>Espaço entre linhas</label><div class="rng"><input id="lg" type="range" min="0" max="10" step="0.5" value="1.5"><b id="lgv">1.5 mm</b></div>
   <div class="btns"><button class="ghost" onclick="resetStretch()">Voltar ao normal</button></div>
  </div>
  <div class="card">
   <h3>Linha e preenchimento</h3>
   <label>Cor da linha</label><input id="cor" type="color" value="#6e9bc4" style="height:40px;padding:2px">
   <div class="sw" id="sw"></div>
   <label>Espessura do traço</label>
   <select id="esp">
    <option value="0|1.0">Fino (igual à fonte)</option>
    <option value="0.3|1.2" selected>Normal — aparece bem no tecido (recomendado)</option>
    <option value="0.6|1.4">Grosso (toalha felpuda, letra pequena)</option>
   </select>
   <label>Preenchimento</label>
   <select id="den">
    <option value="0.50">Mais aberto (tecido fino, menos pontos)</option>
    <option value="0.40" selected>Normal (recomendado)</option>
    <option value="0.34">Mais fechado (cobre mais, toalha/felpudo)</option>
   </select>
  </div>
 </div>
 <div>
  <div class="card">
   <h3>Prévia (como a máquina vai bordar)</h3>
   <div id="pv"><span class="muted">gerando…</span></div>
   <div class="ficha" id="ficha"></div>
   <label>Nome do arquivo</label><input id="nome" value="Felipe">
   <div class="btns">
    <button onclick="baixar()">⬇️ Baixar .pes</button>
    <button class="ghost" onclick="salvar()">💾 Salvar no catálogo</button>
   </div>
   <label>Enviar direto para a máquina</label>
   <div class="two"><select id="maq"></select><button onclick="enviar()">📤 Enviar</button></div>
   <div class="msg" id="msg"></div>
  </div>
 </div>
</div></div>
<script>
const $=s=>document.querySelector(s);
let FONTS=[],font='great_vibes',timer=null,busy=false,pending=false;
const SW=['#ffffff','#f3eee2','#e8a0b0','#f6d66e','#d4a017','#6e9bc4','#a8acb2','#d4af37','#9aae78','#222222'];
function params(){return {text:$('#txt').value,font,max_w:parseFloat($('#maxw').value)||null,max_h:parseFloat($('#maxh').value)||null,
 stretch_x:+$('#sx').value,stretch_y:+$('#sy').value,spacing_mm:+$('#sp').value,line_gap_mm:+$('#lg').value,
 color:$('#cor').value,density:+$('#den').value,bold:+$('#esp').value.split('|')[0],min_w:+$('#esp').value.split('|')[1]};}
function labels(){$('#sxv').textContent=$('#sx').value+'%';$('#syv').textContent=$('#sy').value+'%';
 $('#spv').textContent=(+$('#sp').value).toFixed(1).replace('.',',')+' mm';$('#lgv').textContent=(+$('#lg').value).toFixed(1).replace('.',',')+' mm';}
function resetStretch(){$('#sx').value=100;$('#sy').value=100;$('#sp').value=0;$('#lg').value=1.5;labels();sched();}
function sched(){labels();clearTimeout(timer);timer=setTimeout(prev,450);}
function fmt(n){return String(n).replace('.',',');}
async function prev(){
 if(busy){pending=true;return;} busy=true;
 $('#pv').style.opacity=.5;
 try{const r=await fetch('/api/lettering/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params())});
  const d=await r.json();
  if(!d.ok){$('#pv').innerHTML='<span class="er">'+d.error+'</span>';$('#ficha').innerHTML='';}
  else{$('#pv').innerHTML=d.svg;
   $('#ficha').innerHTML=[['Largura',fmt(d.width_mm)+' mm'],['Altura',fmt(d.height_mm)+' mm'],['Pontos',d.stitches.toLocaleString('pt-BR')],
    ['Cortes de linha',d.trims],['Tempo aprox.',fmt(d.minutes)+' min'],['Tamanho da letra',fmt(d.font_mm)+' mm']]
    .map(([k,v])=>'<div><div class="k">'+k+'</div><div class="v">'+v+'</div></div>').join('');}
 }catch(e){$('#pv').innerHTML='<span class="er">'+e+'</span>';}
 $('#pv').style.opacity=1;busy=false;if(pending){pending=false;prev();}
}
function fname(){return ($('#nome').value||'letreiro').replace(/[^\w\-À-ſ ]/g,'').trim()||'letreiro';}
async function baixar(){
 const r=await fetch('/api/lettering/pes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(params())});
 if(!r.ok){msg((await r.json()).error,false);return;}
 const b=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=fname()+'.pes';a.click();msg('Arquivo baixado.',true);
}
async function salvar(){
 const d=await (await fetch('/api/lettering/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...params(),name:fname()})})).json();
 msg(d.ok?('Salvo no catálogo: '+d.name):d.error,d.ok);
}
async function enviar(){
 msg('Enviando…',true);
 const ipq=encodeURIComponent($('#maq').value);
 const d=await (await fetch('/api/lettering/send?ip='+ipq,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...params(),name:fname()})})).json();
 msg(d.ok?('Enviado para a máquina: '+d.name):(d.error||'falhou'),d.ok);
}
function msg(t,ok){$('#msg').className='msg '+(ok?'ok':'er');$('#msg').textContent=t;}
async function init(){
 const d=await (await fetch('/api/lettering/fonts')).json();FONTS=d.fonts;
 $('#ff').textContent=FONTS.map(f=>"@font-face{font-family:'f_"+f.key+"';src:url('/fonts/"+encodeURIComponent(f.file)+"')}").join('');
 $('#fonts').innerHTML=FONTS.map(f=>'<div class="font'+(f.key==font?' sel':'')+'" data-k="'+f.key+'" title="'+f.desc+'"><div class="s" style="font-family:f_'+f.key+'">Abc</div><div class="n">'+f.name+'</div></div>').join('');
 document.querySelectorAll('.font').forEach(el=>el.onclick=()=>{font=el.dataset.k;document.querySelectorAll('.font').forEach(x=>x.classList.toggle('sel',x===el));sched();});
 $('#sw').innerHTML=SW.map(c=>'<i style="background:'+c+'" data-c="'+c+'"></i>').join('');
 document.querySelectorAll('#sw i').forEach(el=>el.onclick=()=>{$('#cor').value=el.dataset.c;sched();});
 ['txt','maxw','maxh','sx','sy','sp','lg','cor','den','esp'].forEach(id=>$('#'+id).addEventListener('input',sched));
 $('#txt').addEventListener('input',()=>{$('#nome').value=$('#txt').value.split('\n').join(' ').trim().slice(0,40);});
 try{const m=await (await fetch('/api/machines')).json();$('#maq').innerHTML=(m.machines||[]).map(x=>'<option value="'+x.ip+'">'+(x.name||x.ip)+' ('+x.ip+')</option>').join('');}catch(e){}
 labels();prev();
}
init();
</script></body></html>"""
