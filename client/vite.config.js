import react from '@vitejs/plugin-react';
import path from 'node:path';
import { createLogger, defineConfig, loadEnv } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

const isDev = process.env.NODE_ENV !== 'production';
let inlineEditPlugin, editModeDevPlugin;

if (isDev) {
	inlineEditPlugin = (await import('./plugins/visual-editor/vite-plugin-react-inline-editor.js')).default;
	editModeDevPlugin = (await import('./plugins/visual-editor/vite-plugin-edit-mode.js')).default;
}

const configHorizonsViteErrorHandler = `
const observer = new MutationObserver((mutations) => {
	for (const mutation of mutations) {
		for (const addedNode of mutation.addedNodes) {
			if (
				addedNode.nodeType === Node.ELEMENT_NODE &&
				(
					addedNode.tagName?.toLowerCase() === 'vite-error-overlay' ||
					addedNode.classList?.contains('backdrop')
				)
			) {
				handleViteOverlay(addedNode);
			}
		}
	}
});

observer.observe(document.documentElement, {
	childList: true,
	subtree: true
});

function handleViteOverlay(node) {
	if (!node.shadowRoot) {
		return;
	}

	const backdrop = node.shadowRoot.querySelector('.backdrop');

	if (backdrop) {
		const overlayHtml = backdrop.outerHTML;
		const parser = new DOMParser();
		const doc = parser.parseFromString(overlayHtml, 'text/html');
		const messageBodyElement = doc.querySelector('.message-body');
		const fileElement = doc.querySelector('.file');
		const messageText = messageBodyElement ? messageBodyElement.textContent.trim() : '';
		const fileText = fileElement ? fileElement.textContent.trim() : '';
		const error = messageText + (fileText ? ' File:' + fileText : '');

		window.parent.postMessage({
			type: 'horizons-vite-error',
			error,
		}, '*');
	}
}
`;

const configHorizonsRuntimeErrorHandler = `
window.onerror = (message, source, lineno, colno, errorObj) => {
	const errorDetails = errorObj ? JSON.stringify({
		name: errorObj.name,
		message: errorObj.message,
		stack: errorObj.stack,
		source,
		lineno,
		colno,
	}) : null;

	window.parent.postMessage({
		type: 'horizons-runtime-error',
		message,
		error: errorDetails
	}, '*');
};
`;

const configHorizonsConsoleErrroHandler = `
const originalConsoleError = console.error;
console.error = function(...args) {
	originalConsoleError.apply(console, args);

	let errorString = '';

	for (let i = 0; i < args.length; i++) {
		const arg = args[i];
		if (arg instanceof Error) {
			errorString = arg.stack || \`\${arg.name}: \${arg.message}\`;
			break;
		}
	}

	if (!errorString) {
		errorString = args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' ');
	}

	window.parent.postMessage({
		type: 'horizons-console-error',
		error: errorString
	}, '*');
};
`;

const configWindowFetchMonkeyPatch = `
const originalFetch = window.fetch;

window.fetch = function(...args) {
	const url = args[0] instanceof Request ? args[0].url : args[0];

	// Skip WebSocket URLs
	if (url.startsWith('ws:') || url.startsWith('wss:')) {
		return originalFetch.apply(this, args);
	}

	return originalFetch.apply(this, args)
		.then(async response => {
			const contentType = response.headers.get('Content-Type') || '';

			// Exclude HTML document responses
			const isDocumentResponse =
				contentType.includes('text/html') ||
				contentType.includes('application/xhtml+xml');

			if (!response.ok && !isDocumentResponse) {
					const responseClone = response.clone();
					const errorFromRes = await responseClone.text();
					const requestUrl = response.url;
					console.error(\`Fetch error from \${requestUrl}: \${errorFromRes}\`);
			}

			return response;
		})
		.catch(error => {
			if (!url.match(/\.html?$/i)) {
				console.error(error);
			}

			throw error;
		});
};
`;

const addTransformIndexHtml = {
	name: 'add-transform-index-html',
	transformIndexHtml(html) {
		return {
			html,
			tags: [
				{
					tag: 'script',
					attrs: { type: 'module' },
					children: configHorizonsRuntimeErrorHandler,
					injectTo: 'head',
				},
				{
					tag: 'script',
					attrs: { type: 'module' },
					children: configHorizonsViteErrorHandler,
					injectTo: 'head',
				},
				{
					tag: 'script',
					attrs: { type: 'module' },
					children: configHorizonsConsoleErrroHandler,
					injectTo: 'head',
				},
				{
					tag: 'script',
					attrs: { type: 'module' },
					children: configWindowFetchMonkeyPatch,
					injectTo: 'head',
				},
			],
		};
	},
};

console.warn = () => { };

const logger = createLogger()
const loggerError = logger.error

logger.error = (msg, options) => {
	if (options?.error?.toString().includes('CssSyntaxError: [postcss]')) {
		return;
	}

	loggerError(msg, options);
}

export default defineConfig(({ mode }) => {
	const env = loadEnv(mode, process.cwd(), '');
	const backendUrl = env.VITE_BACKEND_URL || 'http://backend:8001';

	return {
		customLogger: logger,
		plugins: [
			...(isDev ? [inlineEditPlugin(), editModeDevPlugin()] : []),
			react(),
			addTransformIndexHtml,
			VitePWA({
				registerType: 'autoUpdate',
				includeAssets: ['favicon-naraedu.ico', 'apple-touch-icon.png'],
				manifest: {
					id: '/',
					name: 'NARA Educacional',
					short_name: 'NARA',
					description: 'Plataforma pedagógica NARA — registros, portfólio e relatórios',
					start_url: '/',
					scope: '/',
					display: 'standalone',
					background_color: '#ffffff',
					theme_color: '#b8ace1',
					orientation: 'portrait-primary',
					icons: [
						{
							src: '/pwa-192x192.png',
							sizes: '192x192',
							type: 'image/png',
						},
						{
							src: '/pwa-512x512.png',
							sizes: '512x512',
							type: 'image/png',
						},
						{
							src: '/pwa-512x512-maskable.png',
							sizes: '512x512',
							type: 'image/png',
							purpose: 'maskable', // necessário pro Android não cortar o ícone
						},
					],
				},
				workbox: {
					maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
					runtimeCaching: [
						{
							urlPattern: ({ url, request }) =>
								request.method === 'GET' && url.pathname.startsWith('/api/'),
							handler: 'NetworkFirst',
							options: {
								cacheName: 'api-get-cache',
								networkTimeoutSeconds: 5,
								cacheableResponse: { statuses: [0, 200] },
								expiration: { maxEntries: 100, maxAgeSeconds: 60 * 60 * 24 },
							},
						},
						{
							urlPattern: ({ url }) => url.pathname.startsWith('/api/auth/'),
							handler: 'NetworkOnly',
						},
						{
							urlPattern: ({ url }) => url.pathname.startsWith('/api/arquivo/'),
							handler: 'CacheFirst',
							options: {
								cacheName: 'arquivos-cache',
								expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 },
							},
						},
					],

					navigateFallbackDenylist: [/^\/api\//],
				},
				devOptions: {
					enabled: false,
				},

			}),
		],
		server: {
			host: '0.0.0.0',
			port: 5173,
			cors: true,
			headers: {
				'Cross-Origin-Embedder-Policy': 'credentialless',
			},
			allowedHosts: true,
			proxy: {
				'/api': {
					target: backendUrl,
					changeOrigin: true,
					secure: false,
				},
				'/static': {
					target: backendUrl,
					changeOrigin: true,
					secure: false,
				},
			},
		},
		resolve: {
			extensions: ['.jsx', '.js', '.tsx', '.ts', '.json',],
			alias: {
				'@': path.resolve(__dirname, './src'),
			},
		},
		preview: {
			host: '0.0.0.0',
			port: 4173,
			proxy: {
				'/api': {
					target: backendUrl,
					changeOrigin: true,
					secure: false,
				},
				'/static': {
					target: backendUrl,
					changeOrigin: true,
					secure: false,
				},
			},
		},
		build: {
			rollupOptions: {
				external: [
					'@babel/parser',
					'@babel/traverse',
					'@babel/generator',
					'@babel/types'
				]
			}
		}
	};
});
