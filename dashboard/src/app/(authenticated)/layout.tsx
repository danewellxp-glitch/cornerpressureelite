"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter, usePathname } from "next/navigation";
import {
    Box,
    Drawer,
    List,
    ListItemIcon,
    ListItemText,
    Typography,
    IconButton,
    Divider,
    Tooltip,
    useMediaQuery,
} from "@mui/material";
import { ThemeProvider, CssBaseline } from "@mui/material";
import {
    Dashboard as DashboardIcon,
    SportsSoccer,
    Style,
    Settings,
    Terminal,
    MenuOpen,
    Menu as MenuIcon,
    Logout,
    History,
} from "@mui/icons-material";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import theme from "@/lib/theme";
import { logout } from "@/lib/api";
import PageTransition from "@/components/PageTransition";

const DRAWER_WIDTH = 260;
const DRAWER_COLLAPSED = 72;

const PURPLE = "#7C4DFF";
const CYAN_GLOW = "drop-shadow(0 0 6px #00E5FF40)";

const NAV_ITEMS = [
    { label: "Dashboard", href: "/dashboard", icon: <DashboardIcon /> },
    { label: "Escanteios", href: "/escanteios", icon: <SportsSoccer /> },
    { label: "Cartões Amarelos", href: "/cartoes-amarelos", icon: <Style /> },
    { label: "Histórico Sinais", href: "/sinais-historico", icon: <History /> },
    { label: "Configurações", href: "/settings", icon: <Settings /> },
    { label: "Logs", href: "/logs", icon: <Terminal /> },
];

type NavItemProps = {
    label: string;
    icon: React.ReactNode;
    open: boolean;
    active: boolean;
    onClick: () => void;
    reduceMotion: boolean;
};

function NavItem({ label, icon, open, active, onClick, reduceMotion }: NavItemProps) {
    return (
        <Tooltip title={!open ? label : ""} placement="right">
            <Box
                component={motion.div}
                initial={false}
                whileHover={reduceMotion ? undefined : "hover"}
                whileTap={reduceMotion ? undefined : { scale: 0.98 }}
                onClick={onClick}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onClick();
                    }
                }}
                sx={{
                    position: "relative",
                    display: "flex",
                    alignItems: "center",
                    gap: 1.5,
                    px: open ? 2 : 1.5,
                    py: 1.1,
                    mb: 0.5,
                    mx: 0.5,
                    borderRadius: 2,
                    cursor: "pointer",
                    color: active ? "#FFFFFF" : "text.secondary",
                    overflow: "hidden",
                    outline: "none",
                    "&:focus-visible": {
                        boxShadow: `0 0 0 2px ${PURPLE}80`,
                    },
                }}
            >
                {/* Active route pill (sliding) */}
                {active && (
                    <motion.div
                        layoutId="active-pill"
                        transition={
                            reduceMotion
                                ? { duration: 0 }
                                : { type: "spring", stiffness: 500, damping: 36 }
                        }
                        style={{
                            position: "absolute",
                            left: 0,
                            top: 6,
                            bottom: 6,
                            width: 4,
                            borderRadius: 2,
                            background: PURPLE,
                            boxShadow: `0 0 12px ${PURPLE}99`,
                        }}
                    />
                )}

                {/* Hover background fade */}
                <Box
                    component={motion.div}
                    variants={{
                        hover: { opacity: 1 },
                    }}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 0 }}
                    transition={{ duration: 0.15, ease: "easeOut" }}
                    sx={{
                        position: "absolute",
                        inset: 0,
                        background: "rgba(124,77,255,0.08)",
                        pointerEvents: "none",
                    }}
                />

                {/* Icon */}
                <Box
                    component={motion.div}
                    variants={{
                        hover: reduceMotion
                            ? {}
                            : { scale: 1.08, filter: CYAN_GLOW },
                    }}
                    transition={{ duration: 0.18, ease: "easeOut" }}
                    sx={{
                        position: "relative",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        minWidth: open ? 32 : "auto",
                        color: active ? PURPLE : "inherit",
                    }}
                >
                    <ListItemIcon sx={{ minWidth: 0, color: "inherit" }}>{icon}</ListItemIcon>
                </Box>

                {/* Label */}
                {open && (
                    <Box
                        component={motion.div}
                        variants={{
                            hover: reduceMotion ? {} : { x: 2 },
                        }}
                        transition={{ duration: 0.18, ease: "easeOut" }}
                        sx={{ position: "relative", flex: 1, minWidth: 0 }}
                    >
                        <ListItemText
                            primary={label}
                            primaryTypographyProps={{
                                fontSize: "0.875rem",
                                fontWeight: active ? 700 : 500,
                                noWrap: true,
                            }}
                        />
                    </Box>
                )}
            </Box>
        </Tooltip>
    );
}

export default function AuthenticatedLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const router = useRouter();
    const isMobile = useMediaQuery(theme.breakpoints.down("md"));
    const [open, setOpen] = useState(!isMobile);
    const reduceMotion = useReducedMotion() ?? false;

    const handleLogout = async () => {
        await logout();
        router.push("/login");
    };

    const drawerWidth = open ? DRAWER_WIDTH : DRAWER_COLLAPSED;

    const drawerContent = (
        <Box sx={{ height: "100%", display: "flex", flexDirection: "column", py: 2 }}>
            {/* Logo + tagline */}
            <Box
                sx={{
                    px: open ? 2.5 : 1,
                    mb: 2,
                    display: "flex",
                    alignItems: "center",
                    gap: 1.25,
                }}
            >
                <Box
                    component={motion.div}
                    initial={reduceMotion ? { opacity: 0 } : { opacity: 0, scale: 0.92 }}
                    animate={reduceMotion ? { opacity: 1 } : { opacity: 1, scale: 1 }}
                    transition={
                        reduceMotion
                            ? { duration: 0.15, ease: "linear" }
                            : { duration: 0.4, ease: [0.34, 1.56, 0.64, 1] }
                    }
                    sx={{
                        position: "relative",
                        width: open ? 40 : 44,
                        height: open ? 40 : 44,
                        flexShrink: 0,
                        borderRadius: "12px",
                        overflow: "hidden",
                    }}
                >
                    <Image
                        src="/brand/logo-mark.png"
                        alt="PressureIQ"
                        fill
                        priority
                        sizes="44px"
                        style={{ objectFit: "contain" }}
                    />
                </Box>
                {open && (
                    <Box
                        component={motion.div}
                        initial={reduceMotion ? { opacity: 0 } : { opacity: 0, x: -6 }}
                        animate={reduceMotion ? { opacity: 1 } : { opacity: 1, x: 0 }}
                        transition={{ duration: 0.35, delay: 0.1, ease: "easeOut" }}
                        sx={{ position: "relative", height: 40, flex: 1, minWidth: 0 }}
                    >
                        <Box sx={{ position: "relative", width: "100%", height: 22 }}>
                            <Image
                                src="/brand/logo-sidebar.png"
                                alt="PressureIQ"
                                fill
                                priority
                                sizes="180px"
                                style={{ objectFit: "contain", objectPosition: "left center" }}
                            />
                        </Box>
                        <Typography
                            variant="caption"
                            sx={{
                                display: "block",
                                color: "#00E5FFCC",
                                fontSize: "0.62rem",
                                fontWeight: 600,
                                letterSpacing: "0.08em",
                                textTransform: "uppercase",
                                lineHeight: 1.1,
                            }}
                        >
                            Corner & Card Pressure Elite
                        </Typography>
                    </Box>
                )}
                <IconButton
                    onClick={() => setOpen(!open)}
                    size="small"
                    sx={{ color: "text.secondary", flexShrink: 0 }}
                    aria-label={open ? "Recolher menu" : "Expandir menu"}
                >
                    {open ? <MenuOpen /> : <MenuIcon />}
                </IconButton>
            </Box>

            <Divider sx={{ mb: 1 }} />

            {/* Nav Items */}
            <List sx={{ flex: 1, px: 0.5 }} component="div">
                <AnimatePresence initial={false}>
                    {NAV_ITEMS.map((item) => (
                        <NavItem
                            key={item.href}
                            label={item.label}
                            icon={item.icon}
                            open={open}
                            active={pathname === item.href}
                            reduceMotion={reduceMotion}
                            onClick={() => {
                                router.push(item.href);
                                if (isMobile) setOpen(false);
                            }}
                        />
                    ))}
                </AnimatePresence>
            </List>

            <Divider sx={{ mt: 1 }} />

            {/* Logout */}
            <Box sx={{ px: 0.5, pt: 1.5 }}>
                <Tooltip title={!open ? "Sair" : ""} placement="right">
                    <Box
                        component={motion.div}
                        whileHover={reduceMotion ? undefined : { x: 2 }}
                        whileTap={reduceMotion ? undefined : { scale: 0.98 }}
                        onClick={handleLogout}
                        role="button"
                        tabIndex={0}
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 1.5,
                            px: open ? 2 : 1.5,
                            py: 1.1,
                            mx: 0.5,
                            borderRadius: 2,
                            cursor: "pointer",
                            color: "text.secondary",
                            transition: "background-color 150ms ease-out, color 150ms ease-out",
                            "&:hover": {
                                bgcolor: "rgba(255,82,82,0.08)",
                                color: "#FF5252",
                            },
                        }}
                    >
                        <ListItemIcon sx={{ minWidth: open ? 32 : "auto", color: "inherit" }}>
                            <Logout fontSize="small" />
                        </ListItemIcon>
                        {open && (
                            <ListItemText
                                primary="Sair"
                                primaryTypographyProps={{ fontSize: "0.875rem", fontWeight: 600 }}
                            />
                        )}
                    </Box>
                </Tooltip>
            </Box>
        </Box>
    );

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <Box sx={{ display: "flex", minHeight: "100vh" }}>
                <Drawer
                    variant={isMobile ? "temporary" : "permanent"}
                    open={isMobile ? open : true}
                    onClose={() => setOpen(false)}
                    sx={{
                        width: drawerWidth,
                        flexShrink: 0,
                        transition: "width 0.2s",
                        "& .MuiDrawer-paper": {
                            width: drawerWidth,
                            overflowX: "hidden",
                            transition: "width 0.2s",
                        },
                    }}
                >
                    {drawerContent}
                </Drawer>

                <Box
                    component="main"
                    sx={{
                        flex: 1,
                        minHeight: "100vh",
                        bgcolor: "background.default",
                        overflow: "auto",
                    }}
                >
                    {isMobile && (
                        <Box sx={{ p: 1, display: "flex", alignItems: "center" }}>
                            <IconButton
                                onClick={() => setOpen(true)}
                                sx={{ color: "text.secondary" }}
                                aria-label="Abrir menu"
                            >
                                <MenuIcon />
                            </IconButton>
                            <Typography variant="subtitle2" fontWeight={700} sx={{ ml: 1 }}>
                                PressureIQ
                            </Typography>
                        </Box>
                    )}
                    <Box sx={{ p: { xs: 2, md: 3 }, maxWidth: 1440, mx: "auto" }}>
                        <PageTransition>{children}</PageTransition>
                    </Box>
                </Box>
            </Box>
        </ThemeProvider>
    );
}
