import asyncio, sys, json, time
sys.path.insert(0, '.')
from sqlalchemy import text
from app.db.session import SessionLocal, engine
from app.db.models import Run
from app.domain.models.enums import Arm, RunStatus
from app.domain.policy.engine import policy_version
from app.domain.constraints.kernel import constraint_version
from app.domain.taxonomy.loader import taxonomy_version
from app.simulation.runner import execute_run
from app.audit.verify import verify_chain
from app.executors.idempotency import STORE

async def one(arm, seed, n):
    async with SessionLocal() as s:
        run = Run(seed=seed, arm=arm, n=n, status=RunStatus.RUNNING,
                  policy_version=policy_version(), taxonomy_version=taxonomy_version(),
                  constraint_version=constraint_version(), llm_mode="STUB")
        s.add(run); await s.flush()
        t0 = time.time()
        m = await execute_run(s, run)
        run.status = RunStatus.COMPLETE; run.metrics = m
        await s.commit()
        return run.id, m, time.time()-t0

async def main():
    async with engine.begin() as c:
        await c.execute(text("TRUNCATE runs, audit_log RESTART IDENTITY CASCADE"))
    out = {}
    for arm in (Arm.DUNNFLOW, Arm.CONTROL):
        rid, m, dt = await one(arm, 42, 400)
        out[arm] = m
        print(f"\n=== {arm} ===  ({dt:.1f}s)")
        rate = m['recovered']/m['cases']
        print(f"  recovery rate      {rate:.4f}  ({m['recovered']}/{m['cases']})")
        print(f"  amount recovered   Rs {m['amount_recovered_minor']//100:,}")
        print(f"  network attempts   {m['network_attempts']}")
        print(f"  duplicate charges  {m['duplicate_charges']}")
        print(f"  compliance viol.   {m['compliance_violations']}")
        print(f"  hard-class retries {m['hard_class_retries']}")
        print(f"  escalated          {m['escalated']}")
        print(f"  refusals           {m['refusals']}")
        if m['tiers']: print(f"  tiers              {m['tiers']}")
        if m.get('duplicate_charge_prevented'): print(f"  DCP                {m['duplicate_charge_prevented']}")
        print(f"  statuses           {m['status_counts']}")
    async with SessionLocal() as s:
        v = await verify_chain(s)
    print(f"\nchain: {v}")
    d, c = out[Arm.DUNNFLOW], out[Arm.CONTROL]
    eff_d = d['amount_recovered_minor']/max(d['network_attempts'],1)
    eff_c = c['amount_recovered_minor']/max(c['network_attempts'],1)
    print(f"\nATTEMPT EFFICIENCY  dunnflow Rs{eff_d/100:,.0f}/call  control Rs{eff_c/100:,.0f}/call  ratio {eff_d/max(eff_c,1):.2f}x")
    await STORE.close(); await engine.dispose()

asyncio.run(main())
