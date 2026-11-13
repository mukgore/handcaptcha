/* Six independently switchable factors; a complete 2^6 design, not user results. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.UIFactorial=api;})(globalThis,()=>{
  'use strict';
  const factors=['selection','overlay','copy','compare','guide','reveal'];
  function condition(value){
    if(typeof value!=='number'||!Number.isInteger(value)||value<0||value>=64)throw Error('Unknown UI condition');
    const result={condition_id:'ui-'+String(value).padStart(2,'0'),mask:value};
    factors.forEach((name,index)=>{result[name]=Boolean(value&(1<<index));});return Object.freeze(result);
  }
  function fromSearch(search){const value=new URLSearchParams(search).get('condition')??'0';
    if(!/^(0|[1-9][0-9]?)$/.test(value))throw Error('Unknown UI condition');return condition(Number(value));}
  function alpha(elapsed,enabled){
    if(typeof elapsed!=='number'||!Number.isFinite(elapsed)||elapsed<0)throw Error('Invalid elapsed time');
    if(typeof enabled!=='boolean')throw Error('Explicit reveal condition required');
    return enabled?Math.max(0,Math.min(1,1-(elapsed-500)/500)):0;
  }
  function order(){return Array.from({length:64},(_,i)=>i).sort((a,b)=>
    factors.filter((_,i)=>a&(1<<i)).length-factors.filter((_,i)=>b&(1<<i)).length||a-b);}
  return Object.freeze({factors:Object.freeze(factors),condition,fromSearch,alpha,order,
    hold_ms:500,fade_ms:500,common_prelude_ms:1000,overlay_opacity:.45});
});
