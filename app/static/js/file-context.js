function permissionsToOctal(permissions) {
    permissions = permissions.slice(1); // Ignore first character
    
    const permissionMap = {
        'r': 4,
        'w': 2,
        'x': 1,
        '-': 0
    };

    let octal = '';

    for (let i = 0; i < permissions.length; i += 3) {
        const triplet = permissions.slice(i, i + 3);
        let groupOctalValue = 0;

        for (let j = 0; j < 3; j++) {
            groupOctalValue += permissionMap[triplet[j]] || 0;
        }

        octal += groupOctalValue;
    }

    return octal;
}

document.addEventListener("DOMContentLoaded", function() {
    const contextMenu = document.getElementById("file-context-menu");
    const fileLinks = document.querySelectorAll(".file-listing");
    
    const editPermissionsPopup = document.getElementById("set-perms-prompt");
    const setGroupInput = document.getElementById("set-group-input");
    const setPermsInput = document.getElementById("set-perms-input");
    const submitPermissionsButton = document.getElementById("set-perms-submit");

    const renamePopup = document.getElementById("rename-prompt");
    const renameInput = document.getElementById("rename-input");
    const submitRenameButton = document.getElementById("rename-submit");

    let currentFileId = null;
    let currentGroup = null;
    let currentPerms = null;
    let currentUser = null;
    let currentName = null;

    fileLinks.forEach(link => {
	link.addEventListener("contextmenu", function(e) {
            e.preventDefault(); // Prevent the default context menu

            currentFileId = link.getAttribute("data-id");
	    currentGroup = link.getAttribute("data-group");
	    currentPerms = permissionsToOctal(link.getAttribute("data-perms"));
	    currentUser = link.getAttribute("data-user");
	    currentName = link.getAttribute("data-name");

            // Show context menu at mouse position
            contextMenu.style.display = "block";
            contextMenu.style.left = `${e.pageX}px`;
            contextMenu.style.top = `${e.pageY}px`;

            document.getElementById("download-option").onclick = function() {
		window.location.href = `/store/download/${fileId}`;
            };

            document.getElementById("rename-option").onclick = function() {
		renamePopup.style.display = "block";
		renameInput.value = currentName;

		renameInput.focus();
		let len = renameInput.value.length;
		renameInput.setSelectionRange(len, len);
            };

	    document.getElementById("edit-perms-option").onclick = function() {
		editPermissionsPopup.style.display = "block";
		setGroupInput.value = currentGroup;
		setPermsInput.value = currentPerms;

		setGroupInput.focus();
		let len = setGroupInput.value.length;
		setGroup.setSelectionRange(len, len);
	    };
	});
    });

    // Hide context menu when clicking anywhere else
    document.addEventListener("click", function() {
	contextMenu.style.display = "none";
    });

    // Handle "Update Permissions" form submission
    submitPermissionsButton.addEventListener("click", function(e) {
        e.preventDefault();

        const newGroup = setGroupInput.value;
        const newPerms = setPermsInput.value;

	if (newGroup !== currentGroup) {
            fetch('/store/set-group', {
		method: 'POST',
		headers: {
                    'Content-Type': 'application/json'
		},
		body: JSON.stringify({
		    user_id: currentUser,
                    file_id: currentFileId,
                    group: newGroup,
		})
            })
		.then(response => response.json())
		.then(data => {
		    if (data.success) {
			location.reload();
		    } else {
			console.error("Error updating group.");
			location.reload();
		    }
		})
		.catch(error => {
		    console.error("Error:", error);
		    location.reload();
		});
	}

	if (newPerms !== currentPerms) {
	    fetch('/store/set-perms', {
		method: 'POST',
		headers: {
                    'Content-Type': 'application/json'
		},
		body: JSON.stringify({
		    user_id: currentUser,
                    file_id: currentFileId,
                    perms: newPerms,
		})
            })
		.then(response => response.json())
		.then(data => {
		    if (data.success) {
			location.reload();
		    } else {
			console.error("Error updating permissions.");
			location.reload();
		    }
		})
		.catch(error => {
		    console.error("Error:", error);
		    location.reload();
		});
	}

        // Close the popup after submitting
        editPermissionsPopup.style.display = "none";
    });

    // Handle "Rename" form submission
    submitRenameButton.addEventListener("click", function(e) {
        e.preventDefault();

        const newName = renameInput.value;

	if (newName) {
	    fetch(`/store/rename`, {
		method: 'POST',
		headers: {
		    'Content-Type': 'application/json'
		},
		body: JSON.stringify({
		    new_name: newName,
		    file_id: currentFileId,
		    user_id: currentUser
		})
	    })
		.then(data => {
		    if (data.ok) {			
			location.reload();
		    } else {
			console.error("Error renaming file");
			location.reload();
		    }
		})
		.catch(error => {
		    console.error("Error:", error);
		    location.reload();
		});
	}
	
        // Close the popup after submitting
        editPermissionsPopup.style.visibility = "hidden";
    });
});
