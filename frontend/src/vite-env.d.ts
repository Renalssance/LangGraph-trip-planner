/// <reference types="vite/client" />

declare module 'ant-design-vue/dist/reset.css'

interface ImportMetaEnv {
  readonly VITE_AMAP_WEB_KEY?: string
  readonly VITE_AMAP_WEB_JS_KEY?: string
  readonly VITE_AMAP_SECURITY_JS_CODE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

interface Window {
  _AMapSecurityConfig?: {
    securityJsCode?: string
    serviceHost?: string
  }
}
