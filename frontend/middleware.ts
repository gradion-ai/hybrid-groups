import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // Only proxy API requests
  if (request.nextUrl.pathname.startsWith('/api/v1/')) {
    const backendUrl = process.env.BACKEND_API_URL || 'http://localhost:8000';
    const url = new URL(request.nextUrl.pathname + request.nextUrl.search, backendUrl);

    return NextResponse.rewrite(url);
  }
}

export const config = {
  matcher: '/api/v1/:path*',
};
