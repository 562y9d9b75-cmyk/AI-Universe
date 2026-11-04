import type { NextConfig } from 'next';
const config:NextConfig={poweredByHeader:false,logging:false,async rewrites(){return [{source:'/api/:path*',destination:`${process.env.AIU_API_ORIGIN||`http://127.0.0.1:${process.env.AIU_PORT||8000}`}/api/:path*`}]},async headers(){return [{source:'/(.*)',headers:[{key:'X-Content-Type-Options',value:'nosniff'},{key:'Referrer-Policy',value:'no-referrer'},{key:'X-Frame-Options',value:'DENY'}]}]}};
export default config;
