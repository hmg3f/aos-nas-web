// System Performance Container
// Will contain performance values to update every second
//
cpu_container = document.getElementById('cpu_container');
disk_usage_container = document.getElementById('disk_usage_container');
log_container = document.getElementById('log_container');

/*
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
                disk_usage_container.textContent = `Total: ${total} \nUsed: ${used} \nFree: ${free} \nPercentage Used: ${percent} % \n`;
		let logs = data.data.logs;
		log_container.textContent = `Logs:\n${logs}`;
	})
}, 1000);

*/
function get_stats() {
	setTimeout(() => {
               	fetch('/system_stats')
               	.then(response => {
                       	return response.json();
               	})
               	.then(data => {
			console.log("updating");
                       	const cpu = data.data.cpu;
                       	cpu_container.textContent = `${cpu}%`;
                        const total = data.data.total;
                        const used = data.data.used;
                        const free = data.data.free;
                        const percent = data.data.percent;
                        disk_usage_container.textContent = `Total: ${total} \nUsed: ${used} \nFree: ${free} \nPercentage Used: ${percent} % \n`;
                        let logs = data.data.logs;
                        log_container.textContent = `Logs:\n${logs}`;
                })
        }, 1000);
}

const get_stat_interval = setInterval(get_stats, 1000);
