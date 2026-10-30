"""Ten bounded, reversible HSS exercises; no client-supplied commands or targets."""
import json
import re

ALARM_GUIDE = 'https://support.huaweicloud.com/usermanual-hss2.0/hss_01_0277.html'
BEST_PRACTICE = 'https://support.huaweicloud.com/bestpractice-hss2.0/hss_06_0040.html'


def scenario(ident, name, phase, description, expected, policy, tools=(), classes=(), types=(), source=ALARM_GUIDE):
    return {'id':ident,'name':name,'phase':phase,'description':description,'expected':expected,
            'policy':policy,'tools':list(tools),'event_classes':list(classes),'event_types':list(types),
            'source':source,'edition_note':'当前使用企业版；以本区域版本能力、策略与规则为准',
            'flow':['operator-network','network-ecs'],'detection_flow':['ecs-hss','hss-alerts','alerts-evidence']}


SCENARIOS = [
    scenario('suid','SUID 文件提权','权限提升','复制 true 为一次性系统测试文件，设置 SUID；不执行提权 Shell。','文件提权 / 设置 suid/sgid','文件提权检测 / HIPS',classes=['fileprotect_0001'],types=[3002],source=BEST_PRACTICE),
    scenario('sgid','SGID 文件提权','权限提升','为另一份一次性 true 副本设置 SGID，演示不同权限位变化。','文件提权 / 设置 suid/sgid','文件提权检测 / HIPS',classes=['fileprotect_0001'],types=[3002],source=BEST_PRACTICE),
    scenario('shell_copy','异常 Shell 副本','执行行为','将 sh 复制到私有样本目录，仅执行固定的 printf 并立即退出。','异常 Shell / 可疑 Shell 行为','恶意文件检测中的异常 Shell',classes=['malware_0001'],types=[3018]),
    scenario('webshell','Webshell 特征文件','恶意文件','在不对外提供 HTTP 的私有目录写入 PHP 检测样本；不访问、不解释执行。','Webshell / 恶意文件','Webshell 检测及对应扫描范围',classes=['webshell_0001','av_1015'],types=[1015]),
    scenario('account','测试账号变更','账号行为','创建密码锁定、无登录 Shell、无 home 的普通系统测试账号，不授予管理员权限。','账号变更相关事件（条件性）','账号异常 / HIPS；普通账号变更不保证告警',classes=['user_1001','user_1002'],types=[4006,4014]),
    scenario('cron','可疑计划任务观测','持久化观测','创建只含 true 的 cron 测试项，日期为不存在的 2 月 31 日，任务不会实际运行。','Crontab 可疑任务 / HIPS','计划任务检测；良性项可能不告警',classes=['crontab_1001'],types=[3027]),
    scenario('port_scan','本机端口探测','发现行为','nmap 仅探测 127.0.0.1 的 8 个固定端口，限速、限时，不扫描外部地址。','高危命令 / 端口扫描 / 可疑扫描（条件性）','高危命令 / 扫描检测；回环流量可能被排除',tools=['nmap'],classes=['procreport_0001','portscan_0001','portscan_0002','hips_0011'],types=[3015,6002,6003],source=BEST_PRACTICE),
    scenario('tcpdump','回环流量采集','高危命令','tcpdump 只采集回环接口的专用测试 UDP 端口，最多 1 个测试包，3 秒超时。','高危命令执行','高危命令策略；不采集业务接口流量',tools=['tcpdump'],classes=['procreport_0001'],types=[3015],source=BEST_PRACTICE),
    scenario('strace','测试进程跟踪','高危命令','strace 只启动并跟踪 true 测试进程，不附加 sshd 或读取凭据。','高危命令执行','高危命令策略；命令行规则可能因策略而异',tools=['strace'],classes=['procreport_0001'],types=[3015],source=BEST_PRACTICE),
    scenario('netcat','回环端口连接','高危命令','nc 连接临时的 127.0.0.1 测试监听端口，仅发送演练字符串，不绑定 Shell。','高危命令执行','高危命令策略；不构造反弹 Shell',tools=['nc'],classes=['procreport_0001'],types=[3015],source=BEST_PRACTICE),
]
BY_ID = {s['id']:s for s in SCENARIOS}


def get_scenario(ident):
    if not isinstance(ident,str) or ident not in BY_ID:
        raise ValueError('未知演练场景')
    return BY_ID[ident]


def match_events(run, events):
    """Evidence is host-scoped upstream, then matched by type, time and new ID."""
    spec=get_scenario(run.get('scenario_id','suid'))
    previous=set(run.get('baseline_event_ids',[]))
    # HSS occurrence timestamps are often rounded to whole seconds. Baseline IDs
    # still exclude pre-existing events within that same second.
    started=int(run.get('started_at') or 0)//1000*1000
    if not started:return []
    matches=[]
    for e in events:
        try:ts=int(e.get('occur_time') or 0);kind=int(e.get('event_type') or 0)
        except (ValueError,TypeError):continue
        if not e.get('event_id') or e['event_id'] in previous or ts<started:continue
        if e.get('event_class_id') in spec['event_classes'] or kind in spec['event_types']:
            matches.append(e)
    return matches


def command_for(ident,token):
    spec=get_scenario(ident)
    if not re.fullmatch('[a-f0-9]{10}',token):raise ValueError('无效演练标识')
    # Only catalog IDs and generated hex tokens enter the remote source.
    setup=f'''import json,os,pathlib,shutil,subprocess,socket,threading,time
ident={ident!r}
token={token!r}
needed={spec['tools']!r}
missing=[tool for tool in needed if not shutil.which(tool)]
if missing: raise SystemExit('缺少工具: '+','.join(missing)+'，请先准备演练依赖')
root=pathlib.Path('/var/lib/hss-demo/scenarios')/token
root.mkdir(parents=True,exist_ok=True,mode=0o700)
os.chmod(root,0o700)
def run(args):
    result=subprocess.run(args,capture_output=True,text=True,timeout=12)
    return {{'exit_code':result.returncode,'output':(result.stdout+result.stderr)[-2400:]}}
result={{'scenario':ident,'marker':token,'exit_code':0}}
'''
    operations={
        'suid':"p=pathlib.Path('/usr/bin/hss_demo_'+token);shutil.copyfile('/usr/bin/true',p);p.chmod(0o4755);result['output']=str(p)+' 4755'",
        'sgid':"p=pathlib.Path('/usr/bin/hss_demo_'+token);shutil.copyfile('/usr/bin/true',p);p.chmod(0o2755);result['output']=str(p)+' 2755'",
        'shell_copy':"p=root/'shell_sample';shutil.copyfile('/bin/sh',p);p.chmod(0o700);result.update(run([str(p),'-c','printf hss-demo-shell']))",
        'webshell':'''p=root/'isolated_sample.php'
p.write_text("<?php /* HSS isolated detector sample, never served or executed */ @eval($_POST['hss_demo']); ?>")
p.chmod(0o600)
result['output']='Isolated detection sample written, no PHP execution: '+str(p)''',
        'account':"result.update(run(['/usr/sbin/useradd','--system','--no-create-home','--shell','/usr/sbin/nologin','hssdemo_'+token]));result['output']+=' locked non-login system account'",
        'cron':"p=pathlib.Path('/etc/cron.d/hss_demo_'+token);p.write_text('# HSS controlled demo - non-existent calendar date\\n0 0 31 2 * root /usr/bin/true\\n');p.chmod(0o600);result['output']='Non-running cron sample: '+str(p)",
        'port_scan':"result.update(run(['nmap','-sT','-n','-Pn','--max-rate','10','--max-retries','0','--host-timeout','8s','-p','22,80,443,8000,8080,8443,18080,18888','127.0.0.1']))",
        'strace':"result.update(run(['strace','-o',str(root/'true.trace'),'/usr/bin/true']))",
        'tcpdump':'''port=39877
p=subprocess.Popen(['tcpdump','-i','lo','-c','1','-w',str(root/'loopback.pcap'),'udp','port',str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
    time.sleep(.5)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:s.sendto(b'hss-demo-loopback-only',('127.0.0.1',port))
    try:out,err=p.communicate(timeout=3)
    except subprocess.TimeoutExpired:p.terminate();out,err=p.communicate(timeout=2)
    result['output']=(out+err).decode(errors='replace')[-2400:]
    result['exit_code']=p.returncode
finally:
    if p.poll() is None:p.kill();p.wait()''',
        'netcat':'''with socket.socket() as listener:
    listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(4)
    port=listener.getsockname()[1]
    def receive():
        try:
            conn,_=listener.accept()
            with conn:conn.settimeout(2);conn.recv(128)
        except (OSError,TimeoutError):pass
    t=threading.Thread(target=receive,daemon=True);t.start()
    p=subprocess.run(['nc','-N','-w','2','127.0.0.1',str(port)],input='hss-demo-loopback-only',capture_output=True,text=True,timeout=5)
    t.join(timeout=4)
    result['exit_code']=p.returncode
    result['output']='Loopback-only TCP sample sent; no shell attached' ''',
    }
    return "python3 - <<'HSS_SCENARIO_PY'\n"+setup+operations[ident]+"\nprint(json.dumps(result,ensure_ascii=False))\nHSS_SCENARIO_PY"


CLEANUP_COMMAND = r'''python3 - <<'HSS_CLEANUP_PY'
import pathlib,re,subprocess,shutil,json
base=pathlib.Path('/var/lib/hss-demo/scenarios')
removed=[]
for d in list(base.iterdir()) if base.exists() else []:
    if not d.is_dir() or d.is_symlink() or not re.fullmatch('[a-f0-9]{10}',d.name):continue
    for p in [pathlib.Path('/usr/bin/hss_demo_'+d.name),pathlib.Path('/etc/cron.d/hss_demo_'+d.name)]:
        if p.exists():p.chmod(0o600);p.unlink()
    user='hssdemo_'+d.name
    check=subprocess.run(['getent','passwd',user],capture_output=True,text=True)
    if check.returncode==0:subprocess.run(['/usr/sbin/userdel',user],check=True)
    shutil.rmtree(d);removed.append(d.name)
for p in pathlib.Path('/usr/bin').glob('hss_demo_*'):
    if re.fullmatch('hss_demo_[a-f0-9]{10}',p.name) and p.is_file() and not p.is_symlink():p.chmod(0o600);p.unlink()
print(json.dumps({'removed_demo_markers':removed,'result':'Only controlled demo artifacts removed'}))
HSS_CLEANUP_PY'''
