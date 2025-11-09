document.addEventListener("DOMContentLoaded", function() {
    const contextMenu = document.getElementById("file-context-menu");
    const fileLinks = document.querySelectorAll(".file-listing");

    fileLinks.forEach(link => {
	link.addEventListener("contextmenu", function(e) {
            e.preventDefault(); // Prevent the default context menu

            const fileId = link.getAttribute("data-id"); // Get file ID

            // Show context menu at mouse position
            contextMenu.style.display = "block";
            contextMenu.style.left = `${e.pageX}px`;
            contextMenu.style.top = `${e.pageY}px`;

            document.getElementById("download-option").onclick = function() {
		window.location.href = `/store/download/${fileId}`;
            };

            document.getElementById("rename-option").onclick = function() {
		const newName = prompt("Enter the new file name:");
		if (newName) {
		    fetch(`/store/rename/${fileId}`, {
			method: 'POST',
			headers: {
			    'Content-Type': 'application/json'
			},
			body: JSON.stringify({ new_name: newName })
		    })
			.then(response => response.json())
			.then(data => {
			    if (data.success) {
				alert("File renamed successfully.");
				link.textContent = newName; // Update displayed file name
			    } else {
				alert("Error renaming file.");
			    }
			});
		}
            };
	});
    });

    // Hide context menu when clicking anywhere else
    document.addEventListener("click", function() {
	contextMenu.style.display = "none";
    });
});
