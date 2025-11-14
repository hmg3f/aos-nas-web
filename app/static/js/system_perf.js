// System Performance Container
// Will contain performance values to update every second
//
cpu_container = document.getElementById('cpu_container');
disk_usage_container = document.getElementById('disk_usage_container');
log_container = document.getElementById('log_container');

function get_stats() {
	setTimeout(() => {
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
			log_container.innerHTML = `<p>Logs:<br><strong>auth.py</strong><br>${logs[0]['auth.log']}<br><br><strong>store.log</strong><br>${logs[1]['store.log']}</p>`;
                })
        }, 1000);
}

const get_stat_interval = setInterval(get_stats, 1000);
