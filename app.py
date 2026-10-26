"""On-demand native WebView shell for the local room workbench."""
from pathlib import Path
import argparse,ctypes,json,logging,os,shutil,sys,tempfile,threading,time,traceback
BASE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
if '--check' in sys.argv:
    import runpy
    runpy.run_path(str(BASE/'check.py'),run_name='__main__')
    raise SystemExit(0)

sys.dont_write_bytecode=True
from backend import Bridge
from singleton import SingleInstance
from bridge_boundary import install_boundary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ui-smoke',action='store_true');parser.add_argument('--smoke-result');args=parser.parse_args()
    import webview
    install_boundary();temp=None
    root=BASE
    if args.ui_smoke:
        temp=tempfile.TemporaryDirectory(prefix='workbench-ui-');root=Path(temp.name)
    bridge=Bridge(root,data_dir=root/'app-data' if temp else BASE/'data');holder={};ready=threading.Event();close_pending=threading.Event()
    def show():
        if ready.wait(10):
            try:holder['window'].restore();holder['window'].show()
            except Exception:logging.exception('Cannot show workbench')
    instance=SingleInstance(BASE if not temp else root,show)
    try:
        if not instance.acquire():return
        entry=BASE/'frontend/dist/index.html'
        if not entry.is_file():raise RuntimeError('工作台前端尚未构建')
        window=webview.create_window('Agent 工作台',str(entry),width=1320,height=860,min_size=(850,640),background_color='#f5f7f8',text_select=True)
        holder['window']=window;window.expose(bridge.call);window.events.shown+=lambda:ready.set()
        def save_export(filename,text):
            selection=window.create_file_dialog(webview.FileDialog.SAVE,save_filename=filename,file_types=('JSON (*.json)',))
            if not selection:return False
            target=Path(selection if isinstance(selection,str) else selection[0])
            target.write_text(text,encoding='utf-8');return True
        bridge.export_saver=save_export
        def closing():
            if bridge._api_active():
                if close_pending.is_set():return False
                answer=ctypes.windll.user32.MessageBoxW(0,'模型仍在回复。是否停止并关闭？\n选择“否”可继续等待。已发送请求可能仍由服务商计费。','Agent 工作台',0x24)
                if answer==6:
                    close_pending.set();bridge._stop_api()
                    def after_stop():
                        while bridge.busy():time.sleep(.1)
                        window.destroy()
                    threading.Thread(target=after_stop,name='close-after-model-stop',daemon=True).start()
                return False
            if bridge.busy():
                ctypes.windll.user32.MessageBoxW(0,'本地操作正在执行，请稍候再关闭。','Agent 工作台',0x40);return False
            return True
        window.events.closing+=closing
        def smoke():
            result={};done=threading.Event()
            try:
                window.events.loaded.wait(25);time.sleep(1)
                def receive(value):result.update(value);done.set()
                window.evaluate_js("""(async()=>{
                    const r=await window.pywebview.api.call('api_bootstrap',{});
                    const workBody=document.body.innerText;
                    const chatButton=Array.from(document.querySelectorAll('button')).find(b=>b.textContent.includes('实验群聊'));
                    if(!chatButton)throw Error('未找到群聊入口');
                    chatButton.click();
                    for(let i=0;i<60&&!document.querySelector('.group-chat');i++)await new Promise(resolve=>setTimeout(resolve,50));
                    return {bridge:r.ok,title:document.title,workBody,chatRendered:!!document.querySelector('.group-chat'),body:document.body.innerText,rootChildren:document.querySelector('#root').childElementCount,overflow:document.documentElement.scrollWidth>innerWidth};
                })()""",callback=receive)
                if not done.wait(20):raise RuntimeError('原生界面没有返回验证结果')
            except Exception as exc:result['error']=str(exc)
            finally:
                if args.smoke_result:Path(args.smoke_result).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
                window.destroy()
        webview.start(smoke if args.ui_smoke else None,gui='edgechromium',debug=False,private_mode=True,storage_path=str((root if temp else BASE)/'data/webview'))
    finally:
        bridge._stop_api()
        instance.close()
        if temp:temp.cleanup()

if __name__=='__main__':
    try:main()
    except Exception as exc:
        if sys.stderr:traceback.print_exc()
        if '--ui-smoke' not in sys.argv:ctypes.windll.user32.MessageBoxW(0,str(exc),'Agent 工作台启动失败',0x10)
        raise SystemExit(1)
