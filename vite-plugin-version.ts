import { Plugin } from 'vite';

export function versionPlugin(): Plugin {
  const version = new Date().getTime().toString();
  
  return {
    name: 'vite-plugin-version',
    transformIndexHtml(html) {
      return html.replace(/__BUILD_VERSION__/g, version);
    },
  };
}
