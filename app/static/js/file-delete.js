document.addEventListener('DOMContentLoaded', function () {
    const selectAllCheckbox = document.getElementById('select-all');
    const deleteButton = document.getElementById('delete-button');
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
		selectedFiles.push(checkbox.getAttribute('data-filename'));
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

	fetch('/store/delete-multiple', {
	  method: 'DELETE',
	  headers: {
	    'Content-Type': 'application/json',
	  },
	  body: JSON.stringify({ files: selectedFiles, path: currentPath }),
	  credentials: 'same-origin'
	})
	  .then(response => {
	    if (response.ok) {
	      alert('Selected items deleted successfully');
	      toggleDeleteButton();
	      setTimeout(() => {
		window.location.reload();
	      }, 1000);
	    } else {
	      response.json().then(d => alert(d.error || 'Error deleting items'));
	    }
	  })
	  .catch(error => {
	    console.error('Error:', error);
	    alert('Error deleting items');
	  });
    });

    // enable/disable delete button based on checkbox selection
    function toggleDeleteButton() {
	const anyChecked = Array.from(fileCheckboxes).some(checkbox => checkbox.checked);
	deleteButton.disabled = !anyChecked;
    }
});
