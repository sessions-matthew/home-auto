import zwavejs from "zwave-js";
import pg from 'pg';
import mqtt from 'mqtt';

import rdln from 'readline';

const readline = rdln.createInterface({
	input: process.stdin,
	output: process.stdout
});

const Controller = zwavejs.Controller;
const Driver = zwavejs.Driver;

// postgres=# create user zwavejs password 'superwavypassword';
// postgres=# create database zwavejs with owner=zwavejs;
// const pool = new pg.Pool({
// 	user: 'zwavejs',
// 	database: 'zwavejs',
// 	password: 'superwavypassword',
// 	port: 5432,
// 	host: 'localhost',
// });

const mqtt_client  = mqtt.connect('mqtt://localhost')

mqtt_client.on('connect', function () {
	console.log("MQTT Connected");
})

// pool.connect((err, client, release) => {
//	 client.query('CREATE TABLE IF NOT EXISTS')
// });

// Tell the driver which serial port to use
const driver = new Driver(
	"/dev/ttyUSB0",
	{
		securityKeys: {
			// These keys are examples, you should initialize yours with random content
			S2_Unauthenticated: Buffer.from(
				"889900aabbccddeef11223344556677f",
				"hex",
			),
			S2_Authenticated: Buffer.from(
				"102030405c0d0e0f006070809000a0b0",
				"hex",
			),
			S2_AccessControl: Buffer.from(
				"1122223aacdddd113334444aabbbbccc",
				"hex",
			),
			// S0_Legacy replaces the old networkKey option
			S0_Legacy: Buffer.from("5060708090102030400a0b0c0d0e0f10", "hex"),
		}
	}
);

driver.updateLogConfig({
	enabled: true,
	// logToFile: true,
	// filename: "/tmp/zwavejs_devicelog.txt"
});

// You must add a handler for the error event before starting the driver
driver.on("error", (e) => {
	// Do something with it
	console.error(e);
});

driver.registerRequestHandler()

function configure_node(value) {
	value.on('value added', (node, args) => {
		console.log('valueadd');
		console.log(node.id);
		console.log(node.deviceClass);
		console.log(args);
	});
	value.on('value removed', (node, args) => {
		console.log('valuerem');
		console.log(node.id);
		console.log(node.deviceClass);
		console.log(args);
	});

	value.on('value updated', (node, args) => {
		if(typeof(args.newValue) == 'boolean') {
			args.newValue = args.newValue  ? 1 : 0
		}
		if(args.commandClass == 113) { // motion basic
			const msg = `${node.id}	Motion	${args.newValue}`;
			mqtt_client.publish('/home/zwave/motion/values', msg);
		} else if(args.commandClass == 49) { // multilevel sensor
			const msg = `${node.id}	${args.property}	${args.newValue}`;
			mqtt_client.publish('/home/zwave/sensor/values', msg);
		} else if(args.commandClass == 32) { // motion notification
			const msg = `${node.id}	${args.property}	${args.newValue}`;
			mqtt_client.publish('/home/zwave/sensor/values', msg);
		} else if(args.commandClass == 128) { // battery
			const msg = `${node.id}	${args.property}	${args.newValue}`;
			mqtt_client.publish('/home/zwave/node/battery', msg);
		} else {
			console.log('valueupdt');
			console.log(node.id);
			console.log(node.deviceClass);
			console.log(args);
		}
	});

	value.on('value notification', (node, args) => {
		if(args.commandClass == 91) { // light switch
			if(args.propertyKey == '002') {
				const msg = `${node.id}	Switch	1`;
				mqtt_client.publish('/home/zwave/switch/values', msg);
			} else if(args.propertyKey == '001') {
				const msg = `${node.id}	Switch	0`;
				mqtt_client.publish('/home/zwave/switch/values', msg);
			} else {
				console.log('valuenotif');
				console.log(node.id);
				console.log(node.deviceClass);
				console.log(args);
			}
		}
	});
}

// Listen for the driver ready event before doing anything with the driver
driver.once("driver ready", async () => {
	console.log("Driver is ready...");

	const nodes = driver.controller.nodes;
	for(const [key, value] of nodes.entries()) {
		configure_node(value);
	}

	mqtt_client.subscribe('/home/zwave/inclusion', function (err) {
		console.log(err);
	});
	mqtt_client.subscribe('/home/zwave/removefailed', function (err) {
		console.log(err);
	});
	
	mqtt_client.publish('/startup', 'zwave');
});

mqtt_client.on('message', function (topic, message) {
	if(topic == '/home/zwave/inclusion') {
		const msg = message.toString();
		const dev = msg.substring(5);
		const idn = msg.substring(0,5);

		driver.controller.beginInclusion({
			strategy: zwavejs.InclusionStrategy.Default,
			userCallbacks: {
				grantSecurityClasses(requested) {
					console.log(requested);
					return new Promise((resolve, reject) => {
						resolve(requested);
					});
				},
				validateDSKAndEnterPIN(dsk) {
					console.log(dsk);
					return new Promise((resolve, reject) => {
						if(dsk == dev) {
							resolve(idn+dsk);
						} else {
							resolve(false);
						}
					});
				},
				abort() {
					console.log('driver aborted');
				}
			}
		});
	} else if(topic == '/home/zwave/removefailed') {
		const id = parseInt(message.toString())
		driver.controller.removeFailedNode(id).then(()=>{
			console.log(`Removed node: ${id}`);
		});
	} else if(topic == '/home/zwave/exclusion') {
		driver.controller.beginExclusion(true);
	}
});

for (const signal of ["SIGINT", "SIGTERM"]) {
	process.on(signal, async () => {
		await driver.destroy();
		process.exit(0);
	});
}

async function start(){
	await driver.start();
}
start();
