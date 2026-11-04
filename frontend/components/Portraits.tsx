'use client';
import {useEffect,useState} from 'react';
import Image from 'next/image';
import {UserRound} from 'lucide-react';
export type CharacterProfile={nationality:string;age_range:string;presentation:string;description:string};
export type PortraitTemplate={id:string;name:string;avatar_url:string;character_profile:CharacterProfile;available?:boolean};
export type AppearanceCatalog={portraits:PortraitTemplate[];nationalities:{value:string;label:string}[];age_ranges:string[];presentations:{value:string;label:string}[];default_portrait_id:string};
const portrait=(id:string,name:string,nationality:string,age_range:string,presentation:string,description:string):PortraitTemplate=>({id,name,avatar_url:`/assets/portraits/${id}.png`,available:true,character_profile:{nationality,age_range,presentation,description}});
export const FALLBACK_CATALOG:AppearanceCatalog={
 portraits:[
  portrait('lin-yuan','林远','CN','40-49','masculine','沉稳、亲切的中国管理者形象。'),
  portrait('shen-zhixia','沈知夏','CN','20-29','feminine','自然、敏锐的中国市场研究者形象。'),
  portrait('zhou-yuan','周予安','CN','30-39','masculine','专注、清晰的中国数据分析师形象。'),
  portrait('su-yining','苏以宁','CN','30-39','feminine','干练、温和的中国产品经理形象。'),
  portrait('chen-yan','陈砚','CN','30-39','masculine','务实、从容的中国工程师形象。'),
  portrait('xu-xinglan','许星澜','CN','30-39','feminine','有个性、富有创意的中国设计师形象。'),
  portrait('gu-mingchuan','顾明川','CN','40-49','masculine','成熟、严谨的中国财务分析师形象。'),
  portrait('lu-jingxing','陆景行','CN','30-39','masculine','开朗、可靠的中国项目经理形象。'),
  portrait('olivia-morgan','奥莉维亚·摩根','GB','30-39','feminine','英国女性职业人士虚拟形象。'),
  portrait('lucas-martin','卢卡斯·马丁','FR','30-39','masculine','法国男性职业人士虚拟形象。')
 ],
 nationalities:[{value:'CN',label:'中国'},{value:'GB',label:'英国'},{value:'FR',label:'法国'}],
 age_ranges:['20-29','30-39','40-49','50-59','60+'],
 presentations:[{value:'masculine',label:'男性化'},{value:'feminine',label:'女性化'},{value:'androgynous',label:'中性'}],
 default_portrait_id:'lin-yuan'
};
const LEGACY:Record<string,string>={Atlas:'lin-yuan',Emma:'shen-zhixia',Alex:'zhou-yuan',Sophia:'su-yining',Mike:'chen-yan',Lily:'xu-xinglan',David:'gu-mingchuan',Noah:'lu-jingxing','林远':'lin-yuan','沈知夏':'shen-zhixia','周予安':'zhou-yuan','苏以宁':'su-yining','陈砚':'chen-yan','许星澜':'xu-xinglan','顾明川':'gu-mingchuan','陆景行':'lu-jingxing'};
export function resolvePortrait(agent:Record<string,any>,catalog:AppearanceCatalog=FALLBACK_CATALOG){
 const appearance=agent.appearance||{};
 const id=appearance.portrait_id||LEGACY[agent.name]||(Number.isInteger(appearance.index)&&appearance.index>=0&&appearance.index<8?FALLBACK_CATALOG.portraits[appearance.index].id:undefined);
 return catalog.portraits.find(p=>p.id===id)||FALLBACK_CATALOG.portraits.find(p=>p.id===id);
}
export function PortraitAvatar({agent,large=false}:{agent:Record<string,any>;large?:boolean}){
 const portrait=resolvePortrait(agent),explicit=agent.appearance?.avatar_url;
 const src=typeof explicit==='string'&&/^\/assets\/portraits\/[a-z0-9-]+\.(png|webp|jpg|jpeg)$/.test(explicit)?explicit:portrait?.avatar_url;
 const [failed,setFailed]=useState(false);
 useEffect(()=>{setFailed(false)},[src]);
 return <span className={'avatar portrait-avatar'+(large?' portrait-large':'')} title="写实虚拟人物头像，不对应真实雇员">{src&&!failed?<Image src={src} alt={`${agent.name}的写实虚拟头像`} fill sizes={large?'(max-width: 700px) 105px, 132px':'(max-width: 700px) 96px, 112px'} quality={75} loading={large?'eager':'lazy'} style={{objectFit:'cover',objectPosition:'center 24%'}} onError={()=>setFailed(true)}/>:<span className="portrait-empty"><UserRound size={large?36:23}/><small>头像待配置</small></span>}</span>
}
export function profileLabel(agent:Record<string,any>){const profile=agent.appearance?.character_profile||resolvePortrait(agent)?.character_profile;return FALLBACK_CATALOG.nationalities.find(n=>n.value===profile?.nationality)?.label||'自定义形象'}
