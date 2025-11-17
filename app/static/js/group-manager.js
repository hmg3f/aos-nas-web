document.addEventListener("DOMContentLoaded", function () {
    const addButton = document.getElementById("group-add");
    const groupItems = document.querySelectorAll('.group');

    addButton.addEventListener("click", function () {
        const groupName = document.getElementById("group-name").value.trim();

        if (groupName === "") {
            console.error("No group name entered");
            return;
        }

        fetch('/auth/group/add', {
            method: 'POST',
            credentials: 'same-origin',
	    headers: {
		'Content-Type': 'application/json',
	    },
	    body: JSON.stringify({
		group: groupName,
	    })
        })
            .then(data => {
		location.reload();
            })
            .catch(error => {
		console.error("Error:", error);
		location.reload();
            });
    });

    groupItems.forEach(item => {
	item.addEventListener('click', function() {
            const groupName = item.getAttribute('data-group');

	    console.log(groupName);

            fetch('/auth/group/remove', {
		method: 'POST',
		credentials: 'same-origin',
		headers: {
		    'Content-Type': 'application/json',
		},
		body: JSON.stringify({
		    group: groupName,
		})
            })
		.then(data => {
		    location.reload();
		})
		.catch(error => {
		    console.error("Error:", error);
		    location.reload();
		});
	});
    });
});
