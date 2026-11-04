'use client';
import {useEffect,useMemo,useRef} from 'react';
import {useFrame} from '@react-three/fiber';
import {useAnimations,useGLTF} from '@react-three/drei';
import {Box3,Group,Vector3} from 'three';
import {clone} from 'three/examples/jsm/utils/SkeletonUtils.js';

export type EmployeeAsset={id:string;name?:string;uri:string;license:string;height?:number;clips:Record<string,string>};
export const LIFE_STATES=['idle','typing','coffee','walking','reading','meeting','whiteboard','resting','returning'] as const;
/** Local, explicitly licensed assets only. A portrait ID survives an employee rename. */
export function validateEmployeeAssets(input:unknown):EmployeeAsset[]{
 if(!Array.isArray(input))return [];
 const used=new Set<string>();
 return input.flatMap((value)=>{
  if(!value||typeof value!=='object')return [];
  const a=value as Partial<EmployeeAsset>;const id=a.id||a.name;
  if(typeof id!=='string'||!id||typeof a.license!=='string'||!a.license.trim()||typeof a.uri!=='string'||!/^\/assets\/employees\/[a-zA-Z0-9/_-]+\.glb$/.test(a.uri)||used.has(id))return [];
  used.add(id);
  const clips=Object.fromEntries(Object.entries(a.clips||{}).filter(([key,value])=>LIFE_STATES.includes(key as typeof LIFE_STATES[number])&&typeof value==='string'));
  return [{id,name:a.name,uri:a.uri,license:a.license,height:typeof a.height==='number'&&a.height>=1.2&&a.height<=2.3?a.height:1.72,clips}];
 });
}
/** Ambient animation reads only employee_animations. It never updates a task or its status.
 * Skeletons are cloned per employee; imported heights are normalized in metres.
 * Missing licensed models are handled by Office as honest portrait location markers.
 */
export default function EmployeeModel({asset,state,seat,index}:{asset:EmployeeAsset;state:string;seat:[number,number,number];index:number}){
 const root=useRef<Group>(null);const {scene,animations}=useGLTF(asset.uri);
 const model=useMemo(()=>{
  const copy=clone(scene);const box=new Box3().setFromObject(copy);const size=box.getSize(new Vector3());const center=box.getCenter(new Vector3());
  const scale=(asset.height||1.72)/Math.max(size.y,.01);
  copy.traverse(o=>{if('isMesh' in o){o.castShadow=true;o.receiveShadow=true}});
  return {scene:copy,scale,offset:[-center.x*scale,-box.min.y*scale,-center.z*scale] as [number,number,number]};
 },[scene,asset.height]);
 const {actions}=useAnimations(animations,root);const elapsed=useRef(0);const current=useRef<string|null>(null);const desired=useMemo(()=>new Vector3(...seat),[seat]);
 const life=LIFE_STATES.includes(state as typeof LIFE_STATES[number])?state:'idle';
 const hasLifeClip=!!actions[asset.clips[life]];
 useEffect(()=>{
  const clip=asset.clips[life]||asset.clips.idle;const next=actions[clip];if(!next)return;
  const previous=current.current?actions[current.current]:null;previous?.fadeOut(.35);next.reset().fadeIn(.35).play();current.current=clip;elapsed.current=0;
  return()=>{next.fadeOut(.2)};
 },[life,asset.clips,actions]);
 useFrame((_,dt)=>{
  if(!root.current)return;elapsed.current+=Math.min(dt,.05);desired.set(...seat);
  if(hasLifeClip){
   if(life==='walking'||life==='returning'){
    const phase=(elapsed.current*.15+index*.17)%2;const progress=phase<1?phase:2-phase;
    desired.z=seat[2]+progress*1.8;root.current.rotation.y=phase<1?0:Math.PI;
   }else if(life==='coffee')desired.set(-7.25,0,-1.4+(index%3)*1.15);
   else if(life==='meeting'||life==='whiteboard')desired.set(7.6+(index%2)*2.8,0,4+(Math.floor(index/2)%3)*1.5);
   else if(life==='resting')desired.set(-9.8+(index%3)*.8,0,3.95);
  }
  root.current.position.lerp(desired,1-Math.exp(-dt*5));
 });
 return <group ref={root} position={seat}><primitive object={model.scene} scale={model.scale} position={model.offset}/></group>;
}
