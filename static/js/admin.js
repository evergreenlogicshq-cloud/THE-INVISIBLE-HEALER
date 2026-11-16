
/**
 * The Invisible Healer
 * Phase 05 - Admin UI Interactions
 *
 * Responsibilities:
 *   - Mobile sidebar navigation
 *   - Keyboard accessibility
 *   - Focus management
 *   - Flash notification dismissal
 *
 * Security:
 *   - No authentication logic.
 *   - No clinical data processing.
 *   - No unsafe innerHTML assignment.
 *   - No sensitive browser storage.
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    initializeSidebar();
    initializeNotifications();
});

/**
 * Initialize responsive sidebar controls.
 */
function initializeSidebar() {
    const sidebar = document.querySelector(
        "#admin-sidebar"
    );

    const toggleButton = document.querySelector(
        "[data-sidebar-toggle]"
    );

    const closeButton = document.querySelector(
        "[data-sidebar-close]"
    );

    const overlay = document.querySelector(
        "[data-sidebar-overlay]"
    );

    if (!sidebar || !toggleButton || !overlay) {
        return;
    }

    let previousFocus = null;

    const focusableSelector = [
        "a[href]",
        "button:not([disabled])",
        "input:not([disabled])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        '[tabindex]:not([tabindex="-1"])'
    ].join(",");

    /**
     * Return whether mobile navigation is active.
     */
    const isMobile = () => {
        return window.matchMedia(
            "(max-width: 900px)"
        ).matches;
    };

    /**
     * Open sidebar.
     */
    function openSidebar() {
        if (!isMobile()) {
            return;
        }

        previousFocus = document.activeElement;

        sidebar.classList.add("is-open");

        overlay.classList.add("is-visible");

        document.body.style.overflow = "hidden";

        toggleButton.setAttribute(
            "aria-expanded",
            "true"
        );

        const firstFocusable = sidebar.querySelector(
            focusableSelector
        );

        if (firstFocusable) {
            firstFocusable.focus();
        }
    }

    /**
     * Close sidebar and restore focus.
     */
    function closeSidebar(restoreFocus = true) {
        sidebar.classList.remove("is-open");

        overlay.classList.remove("is-visible");

        document.body.style.overflow = "";

        toggleButton.setAttribute(
            "aria-expanded",
            "false"
        );

        if (
            restoreFocus &&
            previousFocus &&
            typeof previousFocus.focus === "function"
        ) {
            previousFocus.focus();
        }

        previousFocus = null;
    }

    toggleButton.addEventListener(
        "click",
        openSidebar
    );

    if (closeButton) {
        closeButton.addEventListener(
            "click",
            () => closeSidebar()
        );
    }

    overlay.addEventListener(
        "click",
        () => closeSidebar()
    );

    /**
     * Keyboard controls:
     *   Escape closes navigation.
     *   Tab stays within mobile navigation.
     */
    document.addEventListener(
        "keydown",
        (event) => {
            if (!sidebar.classList.contains("is-open")) {
                return;
            }

            if (event.key === "Escape") {
                closeSidebar();
                return;
            }

            if (event.key !== "Tab") {
                return;
            }

            const elements = Array.from(
                sidebar.querySelectorAll(
                    focusableSelector
                )
            ).filter(
                (element) => element.getClientRects().length > 0
            );

            if (elements.length === 0) {
                return;
            }

            const first = elements[0];
            const last = elements[elements.length - 1];

            if (
                event.shiftKey &&
                document.activeElement === first
            ) {
                event.preventDefault();
                last.focus();
            } else if (
                !event.shiftKey &&
                document.activeElement === last
            ) {
                event.preventDefault();
                first.focus();
            }
        }
    );

    /**
     * Reset mobile state when moving
     * to desktop viewport.
     */
    window.matchMedia(
        "(max-width: 900px)"
    ).addEventListener(
        "change",
        (event) => {
            if (!event.matches) {
                closeSidebar(false);
            }
        }
    );
}

/**
 * Initialize flash notification dismissal.
 */
function initializeNotifications() {
    const dismissButtons = document.querySelectorAll(
        "[data-alert-dismiss]"
    );

    dismissButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const alert = button.closest(
                "[data-dismissible-alert]"
            );

            if (alert) {
                alert.remove();
            }
        });
    });
}
