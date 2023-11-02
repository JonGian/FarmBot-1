 const slider = document.querySelector('.slider-wrapper');
 
 slider.addEventListener('input', ()=>{
	 slider.lastElementChild.innerHTML = slider.firstELementChild.value
	 
 })
 