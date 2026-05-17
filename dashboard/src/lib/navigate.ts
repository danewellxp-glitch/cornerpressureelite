/**
 * Wrapper para `router.push` que usa a View Transitions API (Chrome/Edge 111+,
 * Safari 18+) quando disponível, com fallback para navegação normal.
 *
 * O `viewTransitionName: 'page-content'` no PageTransition declara qual elemento
 * deve participar do morphing — o browser cuida do crossfade automaticamente.
 */
type RouterLike = {
    push: (href: string) => void;
};

type DocWithVT = Document & {
    startViewTransition?: (cb: () => void | Promise<void>) => unknown;
};

export function navigateWithTransition(router: RouterLike, href: string) {
    if (typeof document === "undefined") {
        router.push(href);
        return;
    }
    const doc = document as DocWithVT;
    if (typeof doc.startViewTransition === "function") {
        doc.startViewTransition(() => router.push(href));
    } else {
        router.push(href);
    }
}
