'use client';
import React,{Suspense,useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {Canvas,useFrame,useThree} from '@react-three/fiber';
import {OrbitControls,useGLTF} from '@react-three/drei';
import {ACESFilmicToneMapping,SRGBColorSpace,Vector3} from 'three';
import {Armchair,Building2,Coffee,Eye,Focus,Layers3,Maximize2,Minimize2,MousePointer2,RotateCcw,Users,Video} from 'lucide-react';
import EmployeeModel,{validateEmployeeAssets,type EmployeeAsset} from './EmployeeModel';
import {PortraitAvatar,resolvePortrait} from './Portraits';
import styles from './Office.module.css';
type Row=Record<string,any>;
type Point=[number,number,number];
type Controls={target:Vector3;update:()=>void;enabled:boolean};
type ViewId='overview'|'studio'|'arrival'|'meeting'|'coffee'|'lounge'|'private';
const VIEWS:{id:ViewId;label:string;position:Point;target:Point;icon:typeof Building2;description:string}[]=[
 {id:'overview',label:'总部全景',position:[28,27,32],target:[0,.3,0],icon:Building2,description:'一个完整楼层，八个独立工位与七个共享区域'},
 {id:'studio',label:'开放办公',position:[12,10,15],target:[0,.7,-1.6],icon:Layers3,description:'橡木桌面、声学屏风、自然光与绿植'},
 {id:'arrival',label:'公司大厅',position:[7,5.5,16],target:[0,.9,7],icon:Focus,description:'石材接待台、木格栅与温暖的到达空间'},
 {id:'meeting',label:'会议空间',position:[17,7,13],target:[9,1,5.3],icon:Video,description:'玻璃隔断、八人会议桌与演示区域'},
 {id:'coffee',label:'咖啡吧台',position:[-3,5,7],target:[-10,.9,-.2],icon:Coffee,description:'商用咖啡机、磨豆机与休闲吧台'},
 {id:'lounge',label:'休闲书吧',position:[-2,6.3,15],target:[-9.3,.7,5.8],icon:Armchair,description:'羊毛地毯、布艺沙发、书架与阅读角'},
 {id:'private',label:'独立办公室',position:[-1,7,-.5],target:[-9.2,.9,-6.5],icon:Building2,description:'独立办公、访客座椅与窗边会谈'},
];
const SEATS:Point[]=[[-9.45,0,-5.79],[-4.3,0,.91],[0,0,.91],[4.3,0,.91],[-4.3,0,-3.09],[0,0,-3.09],[4.3,0,-3.09],[9.45,0,-5.79]];
const PORTRAITS=['lin-yuan','shen-zhixia','zhou-yuan','su-yining','chen-yan','xu-xinglan','gu-mingchuan','lu-jingxing'];
const LIFE_LABELS:Record<string,string>={idle:'工位待命',typing:'键盘动作',coffee:'咖啡休息',walking:'走动',reading:'阅读资料',meeting:'会议动作',whiteboard:'白板讨论',resting:'休息',returning:'返回工位'};
class SceneError extends React.Component<{children:React.ReactNode},{error:boolean}>{
 state={error:false};static getDerivedStateFromError(){return {error:true}}
 render(){return this.state.error?<div className={styles.fallback}><h2>办公室资源暂不可用</h2><p>请刷新页面重新加载本地 3D 资产。公司管理与任务功能可以继续使用。</p></div>:this.props.children}
}
function Floor({onReady}:{onReady:()=>void}){
 const {scene}=useGLTF('/assets/headquarters-v2.glb');
 useEffect(()=>{scene.traverse(o=>{if('isMesh' in o){o.castShadow=!o.name.includes('20 Low iron glass');o.receiveShadow=true}});onReady()},[scene,onReady]);
 return <primitive object={scene}/>;
}
/** Project regular DOM labels; avoid nested portals when switching application views. */
function ProjectLabels({root}:{root:React.RefObject<HTMLDivElement|null>}){
 const point=useMemo(()=>new Vector3(),[]);
 useFrame(({camera,size})=>{root.current?.querySelectorAll<HTMLElement>('[data-point]').forEach(el=>{
  const [x,y,z]=el.dataset.point!.split(',').map(Number);point.set(x,y,z).project(camera);
  el.style.left=((point.x+1)/2*size.width)+'px';el.style.top=((-point.y+1)/2*size.height)+'px';
  el.style.visibility=point.z>1||point.z< -1||Math.abs(point.x)>1.1||Math.abs(point.y)>1.1?'hidden':'visible';
 })});return null;
}
function CameraRig({view,revision,controls,moving}:{view:ViewId;revision:number;controls:React.RefObject<Controls|null>;moving:React.RefObject<boolean>}){
 const {camera,invalidate}=useThree();const destination=useMemo(()=>new Vector3(),[]);const target=useMemo(()=>new Vector3(),[]);
 useEffect(()=>{const preset=VIEWS.find(v=>v.id===view)!;destination.set(...preset.position);target.set(...preset.target);moving.current=true;invalidate()},[view,revision,destination,target,moving,invalidate]);
 useFrame((_,dt)=>{
  if(!moving.current||!controls.current)return;
  const rate=1-Math.exp(-Math.min(dt,.05)*5);camera.position.lerp(destination,rate);controls.current.target.lerp(target,rate);controls.current.update();
  if(camera.position.distanceToSquared(destination)<.0004&&controls.current.target.distanceToSquared(target)<.0004){moving.current=false}else invalidate();
 });return null;
}
export default function Office({agents,tasks,animations,onSelect}:{agents:Row[];tasks:Row[];animations:Row[];onSelect:(a:Row)=>void}){
 const [supported,setSupported]=useState<boolean|null>(null);const [quality,setQuality]=useState(true);const [view,setView]=useState<ViewId>('overview');const [revision,setRevision]=useState(0);const [ready,setReady]=useState(false);const [showLabels,setShowLabels]=useState(true);const [roster,setRoster]=useState(false);const [fullscreen,setFullscreen]=useState(false);
 const [employeeAssets,setEmployeeAssets]=useState<EmployeeAsset[]>([]);const labels=useRef<HTMLDivElement>(null);const shell=useRef<HTMLDivElement>(null);const controls=useRef<Controls|null>(null);const moving=useRef(false);
 const onReady=useCallback(()=>setReady(true),[]);
 useEffect(()=>{let active=true;fetch('/assets/manifest.json').then(r=>{if(!r.ok)throw Error('manifest');return r.json()}).then(j=>{if(active)setEmployeeAssets(validateEmployeeAssets(j.employees))}).catch(()=>{});return()=>{active=false}},[]);
 useEffect(()=>{
  const canvas=document.createElement('canvas');const gl=canvas.getContext('webgl2');setSupported(!!gl);setQuality(window.innerWidth>800&&(navigator.hardwareConcurrency||4)>=4);gl?.getExtension('WEBGL_lose_context')?.loseContext();
  const listener=()=>setFullscreen(document.fullscreenElement===shell.current);document.addEventListener('fullscreenchange',listener);return()=>document.removeEventListener('fullscreenchange',listener);
 },[]);
 const positioned=useMemo(()=>{
  const used=new Set<number>();return agents.slice(0,8).map(agent=>{
   const portraitId=agent.appearance?.portrait_id||resolvePortrait(agent)?.id;let index=PORTRAITS.indexOf(portraitId);
   if(index<0||used.has(index))index=SEATS.findIndex((_,i)=>!used.has(i));used.add(index);
   return {agent,index,seat:SEATS[index],portraitId,asset:employeeAssets.find(v=>v.id===portraitId)};
  });
 },[agents,employeeAssets]);
 const activeCount=agents.filter(a=>tasks.some(t=>t.agent_id===a.id&&t.status==='running')).length;
 const preset=VIEWS.find(v=>v.id===view)!;
 async function toggleFullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await shell.current?.requestFullscreen()}catch{/* Embedded browsers may not expose fullscreen. */}}
 function navigate(id:ViewId){setView(id);setRevision(r=>r+1)}
 if(supported===null)return <div className={styles.loading}><div>正在准备总部空间<span>检查设备渲染能力 · 所有资产从本地加载</span></div></div>;
 if(!supported)return <div className={styles.fallback}><h2>当前设备未启用 WebGL 2</h2><p>办公室需要支持 WebGL 2 的浏览器。你仍可查看员工并使用完整管理功能。</p><div className={styles.fallbackTeam}>{agents.map(a=><button key={a.id} onClick={()=>onSelect(a)}>{a.name}<small>{tasks.some(t=>t.agent_id===a.id&&t.status==='running')?'任务执行中':'暂无执行任务'}</small></button>)}</div></div>;
 return <SceneError><div className={`${styles.shell} office-canvas`} ref={shell} data-testid="headquarters-scene">
  <header className={styles.header}><span className={styles.eyebrow}>AI UNIVERSE · HEADQUARTERS / 01</span><h2>在这里，把想法变成成果</h2><div className={styles.subtitle}>{preset.description}</div></header>
  <div className={styles.status}><span className={styles.pill}><i className={styles.dot}/>{activeCount} 人执行任务 / {agents.length} 位员工</span><span className={styles.pill}>{quality?'标准画质':'节能画质'}</span></div>
  <div className={styles.controls}>
   <button title="显示或隐藏员工工位" aria-label="显示或隐藏员工工位" aria-pressed={showLabels} onClick={()=>setShowLabels(v=>!v)}><Eye size={16}/></button>
   <button title="全体员工" aria-label="全体员工" aria-pressed={roster} onClick={()=>setRoster(v=>!v)}><Users size={16}/></button>
   <button title={quality?'切换节能画质':'切换标准画质'} aria-label="切换办公室画质" aria-pressed={quality} onClick={()=>setQuality(v=>!v)}><Layers3 size={16}/></button>
   <button title="重置当前镜头" aria-label="重置当前镜头" onClick={()=>setRevision(r=>r+1)}><RotateCcw size={16}/></button>
   <button title={fullscreen?'退出全屏':'全屏查看'} aria-label={fullscreen?'退出全屏':'全屏查看'} onClick={toggleFullscreen}>{fullscreen?<Minimize2 size={16}/>:<Maximize2 size={16}/>}</button>
  </div>
  {!ready&&<div className={styles.notice} role="status">正在加载本地总部模型，请稍候…</div>}
  <Canvas shadows={quality} frameloop={employeeAssets.length?'always':'demand'} dpr={quality?[1,1.5]:1} camera={{position:[28,27,32],fov:40,near:.1,far:180}} gl={{antialias:quality,alpha:false,toneMapping:ACESFilmicToneMapping,outputColorSpace:SRGBColorSpace}}>
   <color attach="background" args={['#e8e3d9']}/><fog attach="fog" args={['#e8e3d9',65,150]}/><ambientLight intensity={.6}/><hemisphereLight args={['#fff8e9','#9f9c84',1.5]}/>
   <directionalLight position={[-9,22,-6]} intensity={2.7} color="#fff5df" castShadow={quality} shadow-mapSize={[2048,2048]} shadow-camera-left={-21} shadow-camera-right={21} shadow-camera-top={21} shadow-camera-bottom={-21} shadow-camera-near={.5} shadow-camera-far={65} shadow-normalBias={.035} shadow-bias={-.0001}/>
   <directionalLight position={[8,12,14]} intensity={.55} color="#fff6e5"/>
   <mesh rotation={[-Math.PI/2,0,0]} position={[0,-.43,0]} receiveShadow><planeGeometry args={[240,240]}/><meshStandardMaterial color="#e5e0d5" roughness={1}/></mesh>
   <Suspense fallback={null}><Floor onReady={onReady}/>{positioned.map(({agent,index,seat,asset})=>asset?<EmployeeModel key={agent.id} asset={asset} state={animations.find(v=>v.agent_id===agent.id)?.state||'idle'} seat={seat} index={index}/>:null)}</Suspense>
   <ProjectLabels root={labels}/><CameraRig view={view} revision={revision} controls={controls} moving={moving}/>
   <OrbitControls ref={instance=>{controls.current=instance}} makeDefault target={[0,.3,0]} maxPolarAngle={Math.PI/2.13} minPolarAngle={.18} minDistance={4.5} maxDistance={65} enablePan enableDamping dampingFactor={.08} onStart={()=>{moving.current=false}}/>
  </Canvas>
  <div className={styles.labels} ref={labels} style={{display:showLabels&&ready?'block':'none'}}>
   {positioned.map(({agent,seat,asset})=>{const active=tasks.some(t=>t.agent_id===agent.id&&t.status==='running');const life=animations.find(v=>v.agent_id===agent.id)?.state||'idle';return <button key={agent.id} data-point={`${seat[0]},1.8,${seat[2]}`} className={`office-label ${styles.label} ${active?styles.active+' active':''}`} onClick={()=>onSelect(agent)} title={`${agent.name} · ${active?'任务执行中':'暂无执行任务'} · ${asset?LIFE_LABELS[life]||'工位待命':'工位定位，3D 人物待导入'}`}>
    <span className={styles.avatar}><PortraitAvatar agent={agent}/>{active&&<i className={styles.running}/>}</span><span>{agent.name}<small>{active?'任务执行中':'暂无执行任务'}</small></span>
   </button>})}
   {view==='overview'&&[['0,.15,8.8','公司大厅'],['-9,.15,8.8','休闲书吧'],['9,.15,8.8','会议空间'],['-9,.15,-1.7','咖啡吧台'],['0,.15,-8.9','窗边休息区']].map(([point,name])=><span className={styles.zone} key={name} data-point={point}>{name}</span>)}
  </div>
  {roster&&<div className={styles.roster}><strong>全体员工 <small>{agents.length} 位</small></strong><p>头像标记定位工位，点击查看真实任务与记录。</p>{agents.map(agent=><button key={agent.id} onClick={()=>onSelect(agent)}><PortraitAvatar agent={agent}/><span>{agent.name}<small>{agent.role}</small></span><i className={tasks.some(t=>t.agent_id===agent.id&&t.status==='running')?styles.dot:undefined}/></button>)}</div>}
  <div className={styles.bottom}><div className={styles.navigator}><div className={styles.navTitle}><strong>空间导览</strong><span><MousePointer2 size={10} style={{verticalAlign:'middle'}}/> 拖动环绕 · 滚轮缩放 · 右键平移</span></div><div className={styles.rooms}>{VIEWS.map(v=>{const Icon=v.icon;return <button key={v.id} aria-pressed={view===v.id} onClick={()=>navigate(v.id)}><Icon size={13}/>{v.label}</button>})}</div></div><div className={styles.note}><strong>人物与工作，各自真实</strong>{employeeAssets.length?'生活动作单独驱动。任务状态只读取执行记录。':'照片标记员工工位。完整 3D 人物与生活动画等待授权资产导入。'}</div></div>
 </div></SceneError>;
}
