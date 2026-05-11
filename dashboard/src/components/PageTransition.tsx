"use client";

import { usePathname } from "next/navigation";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ReactNode } from "react";

type Props = {
    children: ReactNode;
    routeKey?: string;
};

export default function PageTransition({ children, routeKey }: Props) {
    const pathname = usePathname();
    const reduceMotion = useReducedMotion();
    const key = routeKey ?? pathname;

    if (reduceMotion) {
        return (
            <AnimatePresence mode="wait" initial={false}>
                <motion.div
                    key={key}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.15, ease: "linear" }}
                    style={{ width: "100%" }}
                >
                    {children}
                </motion.div>
            </AnimatePresence>
        );
    }

    return (
        <AnimatePresence mode="wait" initial={false}>
            <motion.div
                key={key}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 0 }}
                transition={{
                    opacity: { duration: 0.25, ease: [0.22, 1, 0.36, 1] },
                    y: { duration: 0.25, ease: [0.22, 1, 0.36, 1] },
                }}
                style={{ width: "100%" }}
            >
                {children}
            </motion.div>
        </AnimatePresence>
    );
}
