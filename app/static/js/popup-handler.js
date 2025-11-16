const popups = document.querySelectorAll('.popup, .prompt');

popups.forEach(popup => {
    const h1 = popup.querySelector('h1');

    h1.addEventListener('click', function(event) {

	if (event.target === h1) {
	    popup.style.display = 'none';
	}
    });
});
