const formData = new FormData();

formData.append('file', fileInput.files[0]);
formData.append('meta', JSON.stringify({description: 'My file'}));

fetch('/add', {
    method: 'POST',
    body: formData
})
    .then(response => response.json())
    .then(data => console.log(data));
