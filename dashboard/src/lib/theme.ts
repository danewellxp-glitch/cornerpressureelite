"use client";

import { createTheme, type Theme, type PaletteColor } from "@mui/material/styles";

const PURPLE = "#7C4DFF";

const bouncePress = "cubic-bezier(0.34, 1.56, 0.64, 1)";

type ButtonColorKey = "primary" | "secondary" | "success" | "error" | "warning" | "info" | "inherit";

const resolveMain = (t: Theme, colorKey: ButtonColorKey): string => {
    if (colorKey === "inherit") return PURPLE;
    const entry = t.palette[colorKey] as PaletteColor | undefined;
    return entry?.main ?? PURPLE;
};

const theme = createTheme({
    palette: {
        mode: "light",
        primary: { main: PURPLE, light: "#B47CFF", dark: "#5C2DC9" },
        secondary: { main: "#0277BD", light: "#40C4FF", dark: "#01579B" },
        success: { main: "#15A34A", light: "#4ADE80", dark: "#0E7A38" },
        error: { main: "#DC2626", light: "#F87171", dark: "#B91C1C" },
        warning: { main: "#B45309", light: "#D97706", dark: "#92400E" },
        background: { default: "#F6F1E7", paper: "#FFFFFF" },
        text: { primary: "#1F1B16", secondary: "#6E6A60" },
        divider: "rgba(31,27,22,0.10)",
    },
    typography: {
        fontFamily: "'Inter', 'Roboto', sans-serif",
        h4: { fontWeight: 700 },
        h5: { fontWeight: 700 },
        h6: { fontWeight: 600 },
        subtitle1: { fontWeight: 500 },
        body2: { color: "#6E6A60" },
    },
    shape: { borderRadius: 12 },
    components: {
        MuiCard: {
            styleOverrides: {
                root: {
                    backgroundImage: "none",
                    backgroundColor: "#FFFFFF",
                    border: "1px solid rgba(31,27,22,0.08)",
                    transition:
                        "border-color 200ms ease-out, box-shadow 200ms ease-out, transform 200ms ease-out",
                    "&:hover": {
                        borderColor: "rgba(124,77,255,0.3)",
                        boxShadow: "0 6px 20px rgba(31,27,22,0.10)",
                    },
                    "@media (prefers-reduced-motion: reduce)": {
                        transition: "border-color 150ms linear",
                        "&:hover": { transform: "none" },
                    },
                },
            },
        },
        MuiCardActionArea: {
            styleOverrides: {
                root: {
                    transition: "transform 200ms ease-out, box-shadow 200ms ease-out",
                    "&:hover": {
                        transform: "scale(1.02)",
                        boxShadow: `0 4px 16px ${PURPLE}40`,
                    },
                    "&:active": {
                        transform: "scale(0.98)",
                        transitionTimingFunction: bouncePress,
                    },
                    "@media (prefers-reduced-motion: reduce)": {
                        transition: "opacity 150ms linear",
                        "&:hover": { transform: "none", boxShadow: "none" },
                        "&:active": { transform: "none" },
                    },
                },
            },
        },
        MuiButton: {
            styleOverrides: {
                root: {
                    textTransform: "none",
                    fontWeight: 600,
                    transition:
                        "transform 200ms ease-out, box-shadow 200ms ease-out, background-color 200ms ease-out, border-color 200ms ease-out, color 200ms ease-out",
                    "&:active": {
                        transform: "scale(0.98)",
                        transitionTimingFunction: bouncePress,
                    },
                    "&.Mui-disabled": {
                        cursor: "not-allowed",
                        transform: "none",
                        boxShadow: "none",
                    },
                    "@media (prefers-reduced-motion: reduce)": {
                        transition:
                            "background-color 150ms linear, color 150ms linear, border-color 150ms linear",
                        "&:hover": { transform: "none", boxShadow: "none" },
                        "&:active": { transform: "none" },
                    },
                },
                contained: ({ ownerState, theme: t }) => {
                    const main = resolveMain(t, (ownerState.color ?? "primary") as ButtonColorKey);
                    return {
                        "&:hover": {
                            transform: "scale(1.02)",
                            boxShadow: `0 4px 16px ${main}40`,
                        },
                    };
                },
                outlined: ({ ownerState, theme: t }) => {
                    const main = resolveMain(t, (ownerState.color ?? "primary") as ButtonColorKey);
                    return {
                        borderWidth: 1,
                        "&:hover": {
                            borderWidth: 2,
                            backgroundColor: `${main}10`,
                        },
                    };
                },
                text: ({ ownerState, theme: t }) => {
                    const main = resolveMain(t, (ownerState.color ?? "primary") as ButtonColorKey);
                    return {
                        position: "relative",
                        "&::after": {
                            content: '""',
                            position: "absolute",
                            left: 12,
                            right: 12,
                            bottom: 6,
                            height: 1,
                            background: main,
                            transform: "scaleX(0)",
                            transformOrigin: "left center",
                            transition: "transform 200ms ease-out",
                        },
                        "&:hover": { backgroundColor: "transparent" },
                        "&:hover::after": { transform: "scaleX(1)" },
                        "@media (prefers-reduced-motion: reduce)": {
                            "&::after": { transition: "none" },
                        },
                    };
                },
            },
        },
        MuiIconButton: {
            styleOverrides: {
                root: {
                    transition:
                        "transform 200ms ease-out, background-color 200ms ease-out, color 200ms ease-out",
                    "&:hover": { transform: "scale(1.15) rotate(5deg)" },
                    "&:active": {
                        transform: "scale(0.92)",
                        transitionTimingFunction: bouncePress,
                    },
                    "&.Mui-disabled": { cursor: "not-allowed", transform: "none" },
                    "@media (prefers-reduced-motion: reduce)": {
                        transition: "background-color 150ms linear, color 150ms linear",
                        "&:hover": { transform: "none" },
                        "&:active": { transform: "none" },
                    },
                },
            },
        },
        MuiToggleButton: {
            styleOverrides: {
                root: () => ({
                    transition:
                        "transform 200ms ease-out, box-shadow 200ms ease-out, background-color 200ms ease-out, color 200ms ease-out",
                    "&:hover": {
                        transform: "scale(1.02)",
                        boxShadow: `0 4px 16px ${PURPLE}40`,
                    },
                    "&:active": {
                        transform: "scale(0.98)",
                        transitionTimingFunction: bouncePress,
                    },
                    "&.Mui-disabled": { cursor: "not-allowed", transform: "none" },
                    "@media (prefers-reduced-motion: reduce)": {
                        transition: "background-color 150ms linear, color 150ms linear",
                        "&:hover": { transform: "none", boxShadow: "none" },
                        "&:active": { transform: "none" },
                    },
                }),
            },
        },
        MuiTextField: {
            styleOverrides: {
                root: {
                    "& .MuiOutlinedInput-root": {
                        "& fieldset": { borderColor: "rgba(31,27,22,0.18)" },
                        "&:hover fieldset": { borderColor: "rgba(124,77,255,0.5)" },
                    },
                },
            },
        },
        MuiDrawer: {
            styleOverrides: {
                paper: {
                    backgroundColor: "#FFFFFF",
                    borderRight: "1px solid rgba(31,27,22,0.10)",
                },
            },
        },
    },
});

export default theme;
