const menuBtn=document.querySelector('.menu-btn');
const nav=document.querySelector('.main-nav');
if(menuBtn&&nav){menuBtn.addEventListener('click',()=>nav.classList.toggle('open'));}
document.querySelectorAll('form[data-demo-form]').forEach(form=>{
 form.addEventListener('submit',e=>{e.preventDefault();const status=form.querySelector('.status'); if(status){status.style.display='block';status.textContent='Thank you. Your information has been received for review.';} form.reset();});
});
