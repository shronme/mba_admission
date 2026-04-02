/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const raw = process.env.NEXT_PUBLIC_API_URL?.trim();
    if (!raw) return [];
    const base = raw.replace(/\/$/, "");
    const dest = /^https?:\/\//i.test(base) ? base : `https://${base}`;
    return [
      {
        source: "/api/:path*",
        destination: `${dest}/:path*`,
      },
    ];
  },
};

export default nextConfig;
