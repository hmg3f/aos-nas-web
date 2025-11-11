document.getElementById('create-folder-button').addEventListener('click', function() {
    const folderName = document.getElementById('new-folder-name').value.trim();
    const status = document.getElementById('folder-status');

    if (!folderName) {
	status.textContent = 'Please enter a folder name.';
	status.className = 'status-error';
	return;
    }

    fetch('/store/create-folder', {
	method: 'POST',
	headers: { 'Content-Type': 'application/json' },
	body: JSON.stringify({
	    folder_name: folderName,
	    path: "{{ current_path }}"
	}),
    })
	.then(r => r.json())
	.then(data => {
	    if (data.error) {
		status.textContent = 'Error: ' + data.error;
		status.className = 'status-error';
	    } else {
		status.textContent = 'Success! Folder created.';
		status.className = 'status-success';
		document.getElementById('new-folder-name').value = '';
		setTimeout(() => { window.location.reload(); }, 1000);
	    }
	})
	.catch(err => {
	    status.textContent = 'Error creating folder: ' + err;
	    status.className = 'status-error';
	});
});
