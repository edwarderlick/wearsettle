const fees = '{"distribution":{"leaderTimeunitsAllocation":"100","validatorTimeunitsAllocation":"200","rotations":["0"],"executionBudgetPerRound":"76548000000000","maxPriceGenPerTimeUnit":"2","storageFeeMaxGasPrice":"300000000","receiptFeeMaxGasPrice":"300000000"}}';
const inv = '[{"id":"wall_scuff","label":"Wall scuff","max_charge_wei":100000000000000},{"id":"missing_remote","label":"TV remote","max_charge_wei":50000000000000}]';
const {execSync} = require('child_process');
const cmd = `genlayer deploy --contract contracts/wearsettle.py --args 0xbb4e0fd1ceac9f8db17242cf86decdcdd45fa48a "https://upload.wikimedia.org/wikipedia/commons/1/15/Hotel_room.jpg" 2592000 2592000 ${JSON.stringify(inv)} --fee-value 76548000002588 --fees ${JSON.stringify(fees)}`;
console.log('Running:', cmd);
execSync(cmd, {stdio: 'inherit', cwd: 'D:\\WearSettle'});
