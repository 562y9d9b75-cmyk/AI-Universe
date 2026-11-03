'use client';
import {useEffect,useRef} from 'react';
import {useFrame} from '@react-three/fiber';
import {useAnimations,useGLTF} from '@react-three/drei';
import {Group} from 'three';
export type EmployeeAsset={name:string;uri:string;license:string;height?:number;clips:Record<string,string>};
export const LIFE_STATES=['idle','typing','coffee','walking','reading','meeting','whiteboard','resting','returning'] as const;
export function validateEmployeeAssets(assets:EmployeeAsset[]){const used=new Set<string>();return assets.filter(a=>{if(!a.name||!a.license||!a.uri.startsWith('/assets/employees/')||a.uri.includes('..')||used.has(a.uri))return false;used.add(a.uri);return true})}
/** Only attached licensed GLBs are rendered. Missing models are never replaced by cartoon people.
 * Life state consumes animation records only; task completion is never written here.
 */
export default function EmployeeModel({asset,state,seat,index}:{asset:EmployeeAsset;state:string;seat:[number,number,number];index:number}){
 const root=useRef<Group>(null);const {scene,animations}=useGLTF(asset.uri);const {actions}=useAnimations(animations,root);
 const elapsed=useRef(0);const current=useRef<string|null>(null);
 useEffect(()=>{const clip=asset.clips[LIFE_STATES.includes(state as typeof LIFE_STATES[number])?state:'idle']||asset.clips.idle;const next=actions[clip];if(!next)return;const previous=current.current?actions[current.current]:null;next.reset().fadeIn(.35).play();previous?.fadeOut(.35);current.current=clip;elapsed.current=0;return()=>{next.fadeOut(.2)}},[state,asset.clips,actions]);
 useFrame((_,dt)=>{if(!root.current)return;elapsed.current+=Math.min(dt,.05);const walking=state==='walking'||state==='returning';if(walking){const cycle=(elapsed.current*.22)%2;const progress=cycle<1?cycle:2-cycle;root.current.position.set(seat[0],seat[1],seat[2]+progress*2.8);root.current.rotation.y=cycle<1?0:Math.PI}else{const offset=state==='coffee'?[-10,0,-4.7]:state==='meeting'||state==='whiteboard'?[8.4,0,3.3]:state==='resting'?[-8,0,3.2]:seat;root.current.position.set(offset[0],offset[1],offset[2]);root.current.rotation.y=0}});
 return <group ref={root} position={seat} scale={asset.height||1}><primitive object={scene}/></group>
}
