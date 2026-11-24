"use strict";

/**
 * Phase 10 - Shared clinical entity frontend.
 */

export function initializeClinicalPage(expectedKind) {
    const root = document.getElementById(
        "clinical-page"
    );

    if (!root || root.dataset.kind !== expectedKind) {
        return;
    }

    const apiBase = root.dataset.apiBase;
    const csrfToken = root.dataset.csrf;

    const feedback = document.getElementById(
        "clinical-feedback"
    );

    const searchInput = document.getElementById(
        "concept-search"
    );

    const conceptSelect = document.getElementById(
        "concept-id"
    );

    const searchStatus = document.getElementById(
        "concept-search-status"
    );

    function showError(message) {
        if (!feedback) {
            return;
        }

        feedback.textContent = message;
        feedback.hidden = false;
        feedback.focus();
    }

    function clearError() {
        if (!feedback) {
            return;
        }

        feedback.textContent = "";
        feedback.hidden = true;
    }

    function resetConceptOptions(message) {
        conceptSelect.replaceChildren();

        const option = document.createElement(
            "option"
        );

        option.value = "";
        option.textContent = message;

        conceptSelect.appendChild(option);
    }

    /**
     * Convert JSON API errors to readable messages.
     */
    function extractError(data) {
        if (typeof data.detail === "string") {
            return data.detail;
        }

        if (Array.isArray(data.detail)) {
            return data.detail.map((item) => {
                const field = Array.isArray(item.loc)
                    ? item.loc.at(-1)
                    : "Field";

                return `${field}: ${item.msg}`;
            }).join("; ");
        }

        return "Unable to complete the operation.";
    }

    /**
     * Concept autocomplete.
     */
    function initializeAutocomplete() {
        if (!searchInput || !conceptSelect || !searchStatus) {
            return;
        }

        let timer = null;
        let controller = null;
        let generation = 0;

        async function searchConcepts(query, requestId) {
            controller = new AbortController();

            const url = new URL(
                `${apiBase}/concept-options`,
                window.location.origin
            );

            url.searchParams.set(
                "q",
                query
            );

            searchStatus.textContent =
                "Searching medical concepts...";

            try {
                const response = await fetch(url, {
                    method: "GET",
                    credentials: "same-origin",
                    cache: "no-store",
                    signal: controller.signal,
                    headers: {
                        Accept: "application/json"
                    }
                });

                if (!response.ok) {
                    throw new Error(
                        "Unable to search medical concepts."
                    );
                }

                const concepts = await response.json();

                // Ignore responses from outdated searches.
                if (requestId !== generation) {
                    return;
                }

                resetConceptOptions(
                    "Select a medical concept"
                );

                if (concepts.length === 0) {
                    searchStatus.textContent =
                        "No available concepts found.";

                    return;
                }

                for (const concept of concepts) {
                    const option = document.createElement(
                        "option"
                    );

                    option.value = concept.id;

                    option.textContent =
                        `${concept.canonical_name} ` +
                        `(${concept.namespace}, ${concept.status})`;

                    conceptSelect.appendChild(option);
                }

                searchStatus.textContent =
                    `${concepts.length} matching concept(s).`;

            } catch (error) {
                if (
                    error.name === "AbortError" ||
                    requestId !== generation
                ) {
                    return;
                }

                resetConceptOptions(
                    "Search failed"
                );

                searchStatus.textContent =
                    "Search failed. Please try again.";
            }
        }

        searchInput.addEventListener("input", () => {
            const query = searchInput.value.trim();

            generation += 1;

            const requestId = generation;

            window.clearTimeout(timer);

            if (controller) {
                controller.abort();
            }

            resetConceptOptions(
                "Search for a concept"
            );

            searchStatus.textContent = "";

            if (!query) {
                return;
            }

            timer = window.setTimeout(() => {
                searchConcepts(
                    query,
                    requestId
                );
            }, 300);
        });
    }

    /**
     * Serialize allowed form fields.
     */
    function serializeForm(form) {
        const values = Object.fromEntries(
            new FormData(form).entries()
        );

        if ("version" in values) {
            values.version = Number(
                values.version
            );
        }

        const nullableFields = [
            "body_system",
            "clinical_category",
            "body_location",
            "symptom_category",
            "notes"
        ];

        for (const field of nullableFields) {
            if (field in values) {
                values[field] =
                    values[field].trim() || null;
            }
        }

        return values;
    }

    /**
     * Protected clinical write operations.
     */
    async function submitForm(form) {
        clearError();

        const operation = form.dataset.operation;

        const conceptId = form.dataset.conceptId;

        const payload = serializeForm(form);

        let endpoint = apiBase;
        let method = "POST";

        if (operation === "update") {
            endpoint =
                `${apiBase}/${encodeURIComponent(conceptId)}`;

            method = "PUT";

        } else if (operation !== "create") {
            endpoint =
                `${apiBase}/${encodeURIComponent(conceptId)}/${operation}`;
        }

        if (operation === "retire") {
            const confirmed = window.confirm(
                "Retire this clinical record? " +
                "Its history will be preserved."
            );

            if (!confirmed) {
                return;
            }
        }

        const buttons = form.querySelectorAll(
            'button[type="submit"]'
        );

        buttons.forEach((button) => {
            button.disabled = true;
        });

        let completed = false;

        try {
            const response = await fetch(endpoint, {
                method,
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken
                },
                body: JSON.stringify(payload)
            });

            let data = {};

            try {
                data = await response.json();
            } catch {
                // Handle non-JSON server responses safely.
            }

            if (!response.ok) {
                throw new Error(
                    extractError(data)
                );
            }

            completed = true;

            // Refresh server-rendered records and versions.
            window.location.assign(
                `/admin/${root.dataset.section}`
            );

        } catch (error) {
            showError(
                error.message ||
                "Unable to complete the operation."
            );

        } finally {
            if (!completed) {
                buttons.forEach((button) => {
                    button.disabled = false;
                });
            }
        }
    }

    /**
     * Initialize forms.
     */
    function initializeForms() {
        root.querySelectorAll(
            "[data-clinical-form]"
        ).forEach((form) => {
            form.addEventListener("submit", (event) => {
                event.preventDefault();

                if (!form.reportValidity()) {
                    return;
                }

                submitForm(form);
            });
        });

        root.querySelectorAll(
            "[data-js-submit]"
        ).forEach((button) => {
            button.disabled = false;
        });
    }

    initializeAutocomplete();
    initializeForms();
}