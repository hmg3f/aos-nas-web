document.addEventListener('DOMContentLoaded', function () {
    const backupSelector = document.getElementById('archive-selector');
    const revertButton = document.getElementById('revert-archive');
    const previousButton = document.getElementById('previous-archive');
    const nextButton = document.getElementById('next-archive');
    
    const diffViewer = document.getElementById('diff-viewer');
    const diffConf = { drawFileList: true,
		       fileListToggle: false,
		       fileListStartVisible: false,
		       fileContentToggle: false,
		       matching: 'lines',
		       outputFormat: 'side-by-side',
		       synchronisedScroll: true,
		       highlight: true,
		       renderNothingWhenEmpty: false,
		       colorScheme: 'dark' };

    function displayDiff(archive) {
	fetch(`/store/diff/${archive}`)
	    .then(response => response.json())
	    .then(data => {
		if (data.diff) {
		    const diffString = data.diff;
		    const diff2htmlUi = new Diff2HtmlUI(diffViewer, diffString, diffConf);

		    diff2htmlUi.draw();
		} else {
		    // Handle case where the 'diff' key is not present in the response
		    console.error('No diff found in the response.');
		    diffViewer.innerHTML = 'Identical to current tree';
		}
	    })
	    .catch(error => {
		console.error('Error fetching the diff:', error);
	    });

    }

    function updateDiff() {
	const selectedArchive = backupSelector.value;
	if (selectedArchive) {
            displayDiff(selectedArchive);
	}
    }
    
    function updateButtons() {
        const options = Array.from(backupSelector.options);
        const selectedIndex = backupSelector.selectedIndex;

        // Disable previous button if at the start
        previousButton.disabled = selectedIndex <= 0;

        // Disable next button if at the end
        nextButton.disabled = selectedIndex >= options.length - 2;

	// Enable revert button if selector has a value
	revertButton.disabled = !backupSelector.value;
    }

    // Update buttons after selection from dropdown
    backupSelector.addEventListener('change', function () {
        updateButtons();

	updateDiff();
    });

    // Handle previous button click
    previousButton.addEventListener('click', function () {
        let selectedIndex = backupSelector.selectedIndex;
        if (selectedIndex > 0) {
            backupSelector.selectedIndex = selectedIndex - 1;
            updateButtons();
        }

	updateDiff();
    });

    // Handle next button click
    nextButton.addEventListener('click', function () {
        let selectedIndex = backupSelector.selectedIndex;
        if (selectedIndex < backupSelector.options.length - 1) {
            backupSelector.selectedIndex = selectedIndex + 1;
            updateButtons();
        }

	updateDiff();
    });

    // Handle revert action
    revertButton.addEventListener('click', function () {
        const selectedBackup = backupSelector.value;
        if (selectedBackup) {
            alert(`Reverting to backup: ${selectedBackup}`);
            // TODO: call restore archive endpoint
        }
    });

    // Initial button states
    updateButtons();
    updateDiff();
});
