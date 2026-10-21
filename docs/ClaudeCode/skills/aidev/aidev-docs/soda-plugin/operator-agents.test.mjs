import {test} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {readFile,rm,mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createAgents,saveSettings,readLedger,loadSettings} from './agents.mjs';

async function fixture(run){
 const root=await mkdtemp(join(tmpdir(),'aidev-operator-'));
 try{
  const calls=[],states=new Map();const now=()=>new Date();
  const taskCall=async(method,p)=>{
   calls.push({method,p});
   if(method==='task.kinds')return {kinds:[{kind:'claude',available:true},{kind:'codex',available:true}]};
   if(method==='task.start'){const requestId=randomUUID();const s={requestId,status:'pending',kind:p.kind};states.set(requestId,s);return s;}
   const s=states.get(p.requestId);if(!s)throw Error('request expired');
   if(method==='task.status')return s;
   if(method==='task.prompt'){s.instruction={state:'queued'};return s;}
   throw Error(method);
  };
  const local=[];const agents=createAgents({taskCall,makeSoda:()=>async(args)=>{local.push(args);throw Error('B CLI must not run');},now});
  const ctx={root,paneId:'app',tabId:'app-tab',workspaceId:'workspace',panes:[]};
  await saveSettings(root,{execution:'operator'});
  await run({root,ctx,agents,calls,states,local});
 }finally{await rm(root,{recursive:true,force:true});}
}
test('操作元の種類を列挙し、Bの導入判定・pane作成なしで監督を要求。重複起動しない',()=>fixture(async({root,ctx,agents,calls,states,local})=>{
 assert.deepEqual((await agents.availableKinds(root)).available,['claude','codex']);
 const r=await agents.startSupervisor(root,ctx,{kind:'codex'});assert.equal(r.status,'pending');
 const start=calls.find(c=>c.method==='task.start');assert.equal(start.p.execution,'operator');assert.equal(start.p.paneId,'app');
 const text=await readFile(join(root,start.p.taskFile),'utf8');assert.match(text,/remote_work/);assert.match(text,/ask_user/);
 await agents.startSupervisor(root,ctx,{kind:'codex'});assert.equal(calls.filter(c=>c.method==='task.start').length,1);
 assert.equal((await readLedger(root)).supervisor.execution,'operator');assert.deepEqual(local,[]);
}));
test('操作元の状態を表示し、追加指示は一意のBファイルをtask.promptへ渡す',()=>fixture(async({root,ctx,agents,calls,states,local})=>{
 const r=await agents.startSupervisor(root,ctx);const s=states.get(r.supervisor.requestId);
 Object.assign(s,{status:'launched',connection:'online',agent:{paneId:'A-pane',state:'idle',updatedAt:Date.now()}});
 assert.equal((await agents.overview(root,[])).supervisor.alive,true);
 assert.equal((await agents.promptSupervisor(root,ctx,{text:'接続先で続けて'})).status,'pending');
 const p=calls.find(c=>c.method==='task.prompt').p;assert.equal(p.paneId,'app');assert.equal(await readFile(join(root,p.taskFile),'utf8'),'接続先で続けて');
 assert.deepEqual(local,[]);
}));
test('担当も操作元で起動し、報告をBの台帳に残す。Bのグラフ・自動終了・resumeを実行しない',()=>fixture(async({root,ctx,agents,calls,states,local})=>{
 const sup=await agents.startSupervisor(root,ctx);Object.assign(states.get(sup.supervisor.requestId),{status:'launched',connection:'online',agent:{paneId:'A-supervisor',state:'idle',updatedAt:Date.now()}});
 const r=await agents.startWorker(root,ctx,{slug:'20261021-test',instruction:'仕様をまとめて',kind:'codex'});
 assert.equal(r.worker.execution,'operator');assert.equal(calls.filter(c=>c.method==='task.start').length,2);
 await agents.reportWorker(root,ctx,{slug:'20261021-test',status:'done',message:'完了'});
 assert.equal((await readLedger(root)).workers['20261021-test'].lastReport.message,'完了');
 assert.equal(await agents.finishDone(root,ctx),0);assert.deepEqual(await agents.related(root,[]),{});
 assert.equal(await agents.captureSessions(root),0);
 await assert.rejects(agents.resumeWorker(root,ctx,{slug:'20261021-test'}));assert.deepEqual(local,[]);
}));
test('状態取得に失敗した操作元の担当へローカルCLIで代行しない',()=>fixture(async({root,ctx,agents,states,local})=>{
 const r=await agents.startSupervisor(root,ctx);states.delete(r.supervisor.requestId);
 await assert.rejects(agents.promptSupervisor(root,ctx,{text:'続けて'}));
 await assert.rejects(agents.startSupervisor(root,ctx));assert.deepEqual(local,[]);
}));
test('操作元では未対応の種類を断り、モデル・権限の引数をBへ渡さない',()=>fixture(async({root,ctx,agents,calls,local})=>{
 await assert.rejects(saveSettings(root,{workerKind:'bob'}));
 await assert.rejects(agents.startSupervisor(root,ctx,{model:'model'}));
 assert.equal((await loadSettings(root)).execution,'operator');assert.deepEqual(calls,[]);assert.deepEqual(local,[]);
}));
