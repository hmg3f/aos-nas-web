const popups = document.querySelectorAll('.popup, .prompt');
const panels = document.querySelectorAll('.panel');

popups.forEach(popup => {
    const h1 = popup.querySelector('h1');

    h1.addEventListener('click', function(event) {

	if (event.target === h1) {
	    popup.style.display = 'none';
	}
    });
});


panels.forEach(panel => {
    const h1 = panel.querySelector('h1');
    const content = panel.querySelector('.content');

    h1.addEventListener('click', function(event) {
	if (event.target === h1) {
	    if (content.style.display === 'none') {
		content.style.display = 'flex';
	    } else {
		content.style.display = 'none';
	    }
	}
    });
});
