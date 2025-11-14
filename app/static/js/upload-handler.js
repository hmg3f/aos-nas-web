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
    document.getElementById('octal-display').textContent = calculateOctalPermissions();
}

document.querySelectorAll('.permissions-grid input[type="checkbox"]').forEach(cb => {
    cb.addEventListener('change', updatePermissionDisplay);
});

document.getElementById('upload-form').addEventListener('submit', function(e) {
    e.preventDefault();

    const fileInput = document.querySelector('input[name="file"]');
    const files = fileInput.files;

    if (!files || files.length === 0) {
        alert("No files selected.");
        return;
    }

    const formData = new FormData();
    const groupInput = document.getElementById('group-input').value;
    const permissions = calculateOctalPermissions();
    const uploadPath = document.getElementById('upload-path').value;

    // append shared attributes
    formData.append("file-group", groupInput);
    formData.append("permissions", permissions);
    formData.append("path", uploadPath);

    // append multiple files
    for (let f of files) {
        formData.append("file[]", f);
    }

    const statusDiv = document.getElementById('upload-status');
    const submitBtn = this.querySelector('button[type="submit"]');

    submitBtn.disabled = true;
    submitBtn.textContent = "Uploading...";
    statusDiv.textContent = "Uploading files...";
    statusDiv.className = "status-info";

    fetch(this.action, {
        method: "POST",
        body: formData
    })
        .then(resp => resp.json())
        .then(data => {
            if (data.error) {
                statusDiv.textContent = "Error: " + data.error;
                statusDiv.className = "status-error";
            } else {
                statusDiv.textContent = `Success! Uploaded ${data.count} file(s).`;
                statusDiv.className = 'status-success';

                document.getElementById("upload-form").reset();
                updatePermissionDisplay();

                setTimeout(() => window.location.reload(), 1800);
            }
        })
        .catch(err => {
            statusDiv.textContent = "Upload failed: " + err.message;
            statusDiv.className = "status-error";
        })
        .finally(() => {
            submitBtn.disabled = false;
            submitBtn.textContent = "Upload";
        });
});

