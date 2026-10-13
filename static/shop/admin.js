document.addEventListener('DOMContentLoaded',()=>{
 const el=document.getElementById('id_currency'); if(!el)return;
 const locale=document.documentElement.lang||'ar'; const names=new Intl.DisplayNames([locale,'en'],{type:'currency'}); const english=new Intl.DisplayNames(['en'],{type:'currency'});
 for(const opt of el.options){try{opt.textContent=`${opt.value} — ${names.of(opt.value)} / ${english.of(opt.value)} — ${new Intl.NumberFormat('en',{style:'currency',currency:opt.value,currencyDisplay:'narrowSymbol'}).format(0).replace(/[\d.,\s]/g,'')}`;}catch{}}
 const search=document.createElement('input');search.type='search';search.placeholder='ابحث عن عملة / Search currency';search.setAttribute('aria-label',search.placeholder);el.before(search);
 search.addEventListener('input',()=>{const q=search.value.toLowerCase();for(const o of el.options)o.hidden=!o.textContent.toLowerCase().includes(q);});
 el.addEventListener('change',()=>{window.alert('تغيير العملة لا يحول الأرقام. حدّث أسعار المنتجات ورسوم التوصيل. الطلبات القديمة تحتفظ بعملتها.');});
});
