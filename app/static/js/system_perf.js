// System Performance Container
// Will contain performance values to update every second
//
cpu_container = document.getElementById('cpu_container');
disk_usage_container = document.getElementById('disk_usage_container');
auth_log_container = document.getElementById('auth_log');
store_log_container = document.getElementById('store_log');

function colorizeLogEntry(logEntry) {
    if (logEntry.includes("::ERROR")) {
        return `<div style="color: #ff6f60;">${logEntry}</div>`;
    } else if (logEntry.includes("::WARNING")) {
        return `<div style="color: #eedd82;">${logEntry}</div>`;
    } else if (logEntry.includes("::INFO")) {
        return `<div style="color: #a6a6a6;">${logEntry}</div>`;
    }
    return logEntry; // Default style for no severity
}

function get_stats() {
    fetch('/system_stats')
        .then(response => {
            return response.json();
        })
        .then(data => {
            const cpu = data.data.cpu;
            cpu_container.textContent = `${cpu}%`;
            const total = data.data.total;
            const used = data.data.used;
            const free = data.data.free;
            const percent = data.data.percent;
            disk_usage_container.innerHTML = `Total: ${total}<br> Used: ${used}<br> Free: ${free}<br> Percentage Used: ${percent} %<br>`;
            let logs = data.data.logs;

	    auth_log = '';
	    for (const line of logs.auth) {
                auth_log += (colorizeLogEntry(line));
	    }
	    auth_log_container.innerHTML = auth_log;

	    store_log = '';
	    for (const line of logs.store) {
		store_log += (colorizeLogEntry(line));
            }
	    store_log_container.innerHTML = store_log;
	})
}

const get_stat_interval = setInterval(get_stats, 2000);
