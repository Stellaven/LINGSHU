import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router'
import { vScrollAutoHide } from './directives/scroll-auto-hide'
import { vSpotlight } from './directives/spotlight'
import './styles/main.css'

createApp(App)
  .use(router)
  .directive('spotlight', vSpotlight)
  .directive('scroll-auto-hide', vScrollAutoHide)
  .mount('#app')
