document.addEventListener('DOMContentLoaded', function () {
    const selectAllCheckbox = document.getElementById('select-all');
    const deleteButton = document.getElementById('delete-button');
    const userId = deleteButton.getAttribute('data-user');
    const fileCheckboxes = document.querySelectorAll('.file-checkbox');

    // select or deselect all checkboxes
    selectAllCheckbox.addEventListener('change', function () {
	const isChecked = selectAllCheckbox.checked;
	fileCheckboxes.forEach(checkbox => {
            checkbox.checked = isChecked;
	});
	toggleDeleteButton();
    });

    // enable/disable the delete button based on checkbox selection
    fileCheckboxes.forEach(checkbox => {
	checkbox.addEventListener('change', toggleDeleteButton);
    });

    // delete selected files when button is clicked
    deleteButton.addEventListener('click', function () {
	const selectedFiles = [];
	
	fileCheckboxes.forEach(checkbox => {
            if (checkbox.checked) {
		selectedFiles.push(checkbox.getAttribute('data-id'));
            }
	});

	if (selectedFiles.length === 0) {
            alert("No files selected for deletion.");
            return;
	}

	// confirmation
	const confirmDelete = confirm(`Are you sure you want to delete ${selectedFiles.length} file(s)?`);
	if (!confirmDelete) {
            return;
	}

	// send DELETE request to the server
	const pageDataEl = document.getElementById('page-data');
	const currentPath = pageDataEl ? pageDataEl.dataset.currentPath || '/' : '/';

	fetch('/store/delete-files', {
	    method: 'DELETE',
	    headers: {
		'Content-Type': 'application/json',
	    },
	    body: JSON.stringify({
		file_ids: selectedFiles,
		path: currentPath,
		user_id: userId
	    }),
	    credentials: 'same-origin'
	})
	    .then(response => {
		if (response.ok) {
		    toggleDeleteButton();
		    setTimeout(() => {
			window.location.reload();
		    }, 1000);
		}
	    })
	    .catch(error => {
		console.error('Error:', error);
	    });
    });

    // enable/disable delete button based on checkbox selection
    function toggleDeleteButton() {
	const anyChecked = Array.from(fileCheckboxes).some(checkbox => checkbox.checked);
	deleteButton.disabled = !anyChecked;
    }
});
