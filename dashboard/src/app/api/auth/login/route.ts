import { NextResponse } from "next/server";
import { SignJWT } from "jose";
import bcryptjs from "bcryptjs";

// Hardcoded admin credentials (override via env)
const ADMIN_EMAIL = process.env.CPES_ADMIN_EMAIL || "admin@cpes.com";
const ADMIN_HASH =
    process.env.CPES_ADMIN_HASH ||
    bcryptjs.hashSync(process.env.CPES_ADMIN_PASSWORD || "cpes2026", 10);
const JWT_SECRET = new TextEncoder().encode(
    process.env.JWT_SECRET || "cpes-jwt-secret-key-2026-super-secure"
);

export async function POST(req: Request) {
    try {
        const { email, password } = await req.json();

        if (!email || !password) {
            return NextResponse.json(
                { error: "Email e senha obrigatórios" },
                { status: 400 }
            );
        }

        if (email !== ADMIN_EMAIL || !bcryptjs.compareSync(password, ADMIN_HASH)) {
            return NextResponse.json(
                { error: "Credenciais inválidas" },
                { status: 401 }
            );
        }

        const token = await new SignJWT({ email, role: "admin" })
            .setProtectedHeader({ alg: "HS256" })
            .setIssuedAt()
            .setExpirationTime("7d")
            .sign(JWT_SECRET);

        const res = NextResponse.json({ success: true });
        res.cookies.set("cpes-auth", token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === "production",
            sameSite: "lax",
            maxAge: 60 * 60 * 24 * 7, // 7 days
            path: "/",
        });
        return res;
    } catch {
        return NextResponse.json({ error: "Erro interno" }, { status: 500 });
    }
}
