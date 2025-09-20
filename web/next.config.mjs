import envPackage from '@next/env';
import { dirname, resolve } from 'path';
import { fileURLToPath } from 'url';

// Ensure the Next.js runtime loads environment variables declared in the repo root .env
const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..');
const isDevelopment = process.env.NODE_ENV !== 'production';

const { loadEnvConfig } = envPackage;
loadEnvConfig?.(repoRoot, isDevelopment);

/** @type {import('next').NextConfig} */
const nextConfig = {};

export default nextConfig;
