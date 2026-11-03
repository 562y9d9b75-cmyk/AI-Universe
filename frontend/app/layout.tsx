import type {Metadata} from 'next';
import './globals.css';
export const metadata:Metadata={title:'AI Universe · 个人 AI 公司',description:'管理你的 AI 员工、任务和工作成果'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="zh-CN"><body>{children}</body></html>}
