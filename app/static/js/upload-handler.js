function calculateOctalPermissions() {
    const perms = ['user', 'group', 'everyone'];
    let octal = '';

    perms.forEach(entity => {
        let value = 0;
	
        if (document.querySelector(`input[name="perm_${entity}_read"]`).checked) value += 4;
        if (document.querySelector(`input[name="perm_${entity}_write"]`).checked) value += 2;
        if (document.querySelector(`input[name="perm_${entity}_execute"]`).checked) value += 1;
	
        octal += value;
    });

    return octal;
}

function updatePermissionDisplay() {
    let octal = calculateOctalPermissions();
    document.getElementById('octal-display').textContent = octal;
}

document.querySelectorAll('.permissions-grid input[type="checkbox"]').forEach(checkbox => {
    checkbox.addEventListener('change', updatePermissionDisplay);
});

document.getElementById('upload-form').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);

    const groupInput = document.getElementById('group-input');
    formData.append('file-group', groupInput.value);
    
    const octal = calculateOctalPermissions();
    formData.append('permissions', octal);
    
    const statusDiv = document.getElementById('upload-status');
    const submitBtn = this.querySelector('button[type="submit"]');
    
    // Disable button and show loading
    submitBtn.disabled = true;
    submitBtn.textContent = 'Uploading...';
    statusDiv.textContent = 'Uploading file...';
    statusDiv.className = 'status-info';
    
    fetch(this.action, {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
		statusDiv.textContent = 'Error: ' + data.error;
		statusDiv.className = 'status-error';
            } else {
		statusDiv.textContent = 'Success! File uploaded: ' + data.filename;
		statusDiv.className = 'status-success';
		
		// Reset form
		document.getElementById('upload-form').reset();
		updatePermissionDisplay();
		
		// Reload page after 2 second to show new file
		setTimeout(() => {
		    window.location.reload();
		}, 2000);
            }
        })
        .catch(error => {
            statusDiv.textContent = 'Upload failed: ' + error.message;
            statusDiv.className = 'status-error';
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Upload';
        });
});
