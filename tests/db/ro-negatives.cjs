/**
 * salon_ro's limits, proven by NEGATIVE tests with a positive control (MIGRATION-PLAN §3g, D2b-3).
 *
 * Connection settings come from the environment (PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD), loaded by the
 * caller from the operator-made, deny-listed file; this script prints NO value, only SQLSTATE codes.
 * No attempt can change data even if a privilege had been granted by mistake: INSERT/UPDATE/DELETE carry
 * `WHERE false` (Postgres checks privileges before execution), and TRUNCATE, CREATE TABLE and CREATE TEMP
 * TABLE, which have no WHERE, run inside BEGIN … ROLLBACK.
 *
 * Run:  set -a; . <the read-only env file>; set +a; node tests/db/ro-negatives.cjs
 */
const path = require('node:path');
const { Client } = require(path.join(__dirname, '..', '..', 'web', 'node_modules', 'pg'));

const TABLES = ['conversations', 'appointments', 'leads', 'processed_messages', 'bot_metrics'];
const results = [];
const record = (label, expect, got) => {
  const ok = expect === got;
  results.push(ok);
  console.log(`${ok ? '✓' : '✗'} ${label.padEnd(54)} expected ${expect.padEnd(7)} got ${got}`);
};

async function code(client, sql) {
  try { await client.query(sql); return 'OK'; } catch (e) { return e.code || 'ERR'; }
}

(async () => {
  if (process.env.PGUSER !== 'salon_ro') throw new Error('PGUSER is not salon_ro — refusing to run');
  const c = new Client();
  await c.connect();
  const who = (await c.query('select current_user as u, current_database() as d')).rows[0];
  record('connected as salon_ro to salon (control)', 'OK', who.u === 'salon_ro' && who.d === 'salon' ? 'OK' : `${who.u}/${who.d}`);

  for (const t of TABLES) record(`SELECT on ${t} (positive control)`, 'OK', await code(c, `select count(*) from salon.${t}`));
  for (const t of TABLES) {
    const col = t === 'bot_metrics' ? 'period_key' : (t === 'leads' ? 'name' : (t === 'appointments' ? 'service' : 'sender_key'));
    record(`INSERT into ${t}`, '42501', await code(c, `insert into salon.${t} (${col}) select 'mig-ro' where false`));
    record(`UPDATE ${t}`, '42501', await code(c, `update salon.${t} set ${col} = ${col} where false`));
    record(`DELETE from ${t}`, '42501', await code(c, `delete from salon.${t} where false`));
  }
  const inTx = async (sql) => { await c.query('begin'); const r = await code(c, sql); await c.query('rollback'); return r; };
  record('TRUNCATE salon.leads (inside a rolled-back tx)', '42501', await inTx('truncate salon.leads'));
  record('CREATE TABLE in schema salon (rolled-back tx)', '42501', await inTx('create table salon.mig_ro_probe (x int)'));
  record('CREATE TEMP TABLE (rolled-back tx)', '42501', await inTx('create temp table mig_ro_probe (x int)'));

  const owner = (await c.query("select rolcanlogin from pg_roles where rolname = 'salon_owner'")).rows[0];
  record('salon_owner cannot log in (catalog: rolcanlogin)', 'false', String(owner && owner.rolcanlogin));
  await c.end();

  const other = new Client({ database: 'postgres' });
  let otherCode;
  try { await other.connect(); otherCode = 'OK'; await other.end(); } catch (e) { otherCode = e.code || 'ERR'; }
  record('connect to database "postgres"', '42501', otherCode);

  const passed = results.filter(Boolean).length;
  console.log(`ro-negatives: ${passed}/${results.length} as expected`);
  process.exit(passed === results.length ? 0 : 1);
})().catch((e) => { console.error('ro-negatives: aborted —', e.code || 'no SQLSTATE'); process.exit(2); });   // code only: a connect error's message carries the host
