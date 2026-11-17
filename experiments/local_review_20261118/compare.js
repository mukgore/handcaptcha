'use strict';
const $=id=>document.getElementById(id),labels={selection:'선택한 손 유지',overlay:'두 영상 겹치기',copy:'안내 문구',compare:'손바닥·손등 그림',guide:'가이드 손금',reveal:'처음 잠깐 보여 주기'};
let at=1250;
function freeze(){let ready=0;for(const id of ['baseline','variant']){const api=$(id).contentWindow?.UIStudy;if(api?.preview){api.freezeAt(at);ready++;}}$('time-status').textContent=`${at}ms · 예시 ${ready}/2 화면 준비` ;}
function setMask(mask){
 $('switches').querySelectorAll('input').forEach((input,i)=>input.checked=Boolean(mask&(1<<i)));
 const c=UIFactorial.condition(mask);$('condition').textContent=c.condition_id;
 $('variant').src='../prod_ui_factorial/run.html?preview=1&condition='+mask;
 $('large').href='../prod_ui_factorial/run.html?preview=1&condition='+mask;
 $('live').href='../prod_ui_factorial/run.html?condition='+mask;
}
UIFactorial.factors.forEach((name,index)=>{const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=name;input.checked=true;input.addEventListener('change',()=>setMask([...$('switches').querySelectorAll('input')].reduce((value,node,i)=>value+(node.checked?(1<<i):0),0)));label.append(input,' '+labels[name]);$('switches').append(label);});
['baseline','variant'].forEach(id=>$(id).addEventListener('load',freeze));
document.querySelectorAll('[data-time]').forEach(button=>button.addEventListener('click',()=>{at=Number(button.dataset.time);freeze();}));
$('all-on').onclick=()=>setMask(63);$('all-off').onclick=()=>setMask(0);setMask(63);
