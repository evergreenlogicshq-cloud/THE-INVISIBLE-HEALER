/**
 * The Invisible Healer
 * Phase 11 - Catalog management interface
 *
 * No client-side clinical decision making.
 * All validation and permissions remain server-side.
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("#catalog-manager");

    if (!root) {
        return;
    }

    const section = root.dataset.section;
    const csrfToken = root.dataset.csrfToken;
    const api = `/api/admin/${section}`;

    const createForm = document.querySelector("#catalog-create-form");
    const editForm = document.querySelector("#catalog-edit-form");
    const dialog = document.querySelector("#catalog-record-dialog");

    const feedback = document.querySelector("#catalog-feedback");
    const dialogFeedback = document.querySelector(
        "#catalog-dialog-feedback"
    );

    const conceptSearch = document.querySelector(
        "#catalog-concept-search"
    );

    const conceptSelect = createForm.elements.namedItem(
        "concept_id"
    );

    const reviewNotes = document.querySelector(
        "#catalog-review-notes"
    );

    let currentRecord = null;
    let busy = false;

    function showFeedback(message, isError = false) {
        const target = dialog.open
            ? dialogFeedback
            : feedback;

        target.hidden = false;
        target.textContent = message;
        target.dataset.error = String(isError);
    }

    async function request(url, method = "GET", body = null) {
        const headers = {
            "Accept": "application/json",
            "X-CSRF-Token": csrfToken,
        };

        const options = {
            method,
            headers,
            credentials: "same-origin",
            cache: "no-store",
        };

        if (body !== null) {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }

        const response = await fetch(url, options);

        let data;

        try {
            data = await response.json();
        } catch {
            throw new Error(
                "Unexpected server response. Please sign in again."
            );
        }

        if (!response.ok) {
            const detail = data.detail;

            if (Array.isArray(detail)) {
                throw new Error(
                    detail.map((item) => item.msg).join("; ")
                );
            }

            throw new Error(
                typeof detail === "string"
                    ? detail
                    : "The request could not be completed."
            );
        }

        return data;
    }

    function getPayload(form) {
        const data = {};

        for (const [key, value] of new FormData(form)) {
            const cleaned = String(value).trim();

            data[key] = key === "description"
                ? cleaned
                : cleaned || null;
        }

        return data;
    }

    async function perform(operation) {
        if (busy) {
            return;
        }

        busy = true;

        try {
            await operation();
        } catch (error) {
            showFeedback(error.message, true);
        } finally {
            busy = false;
        }
    }

    // ==========================================
    // CONCEPT AUTOCOMPLETE
    // ==========================================

    conceptSearch.addEventListener("input", () => {
        conceptSelect.replaceChildren(new Option("Search and select a concept", ""));
    });

    document.querySelector(
        "#catalog-concept-search-button"
    ).addEventListener("click", () => {
        perform(async () => {
            const query = conceptSearch.value.trim();

            if (!query) {
                throw new Error(
                    "Enter a medical concept name."
                );
            }

            const records = await request(
                `${api}/concept-options?q=${encodeURIComponent(query)}`
            );

            if (conceptSearch.value.trim() !== query) {
                return;
            }

            conceptSelect.replaceChildren();

            const placeholder = document.createElement("option");

            placeholder.value = "";
            placeholder.textContent = "Select a medical concept";

            conceptSelect.appendChild(placeholder);

            for (const record of records) {
                const option = document.createElement("option");

                option.value = record.id;

                option.textContent = (
                    `${record.canonical_name} — ${record.status}`
                );

                conceptSelect.appendChild(option);
            }

            showFeedback(
                records.length
                    ? `${records.length} concept(s) found.`
                    : "No available concepts found."
            );
        });
    });

    // ==========================================
    // CREATE DRAFT
    // ==========================================

    createForm.addEventListener("submit", (event) => {
        event.preventDefault();

        perform(async () => {
            await request(
                api,
                "POST",
                getPayload(createForm)
            );

            window.location.reload();
        });
    });

    // ==========================================
    // RENDER RECORD
    // ==========================================

    function renderRecord(record) {
        currentRecord = record;

        document.querySelector(
            "#catalog-record-title"
        ).textContent = record.canonical_name;

        document.querySelector(
            "#catalog-record-status"
        ).textContent = (
            `Status: ${record.status} | Version: ${record.version}`
        );

        const isDraft = record.status === "draft";

        for (const element of editForm.elements) {
            if (!element.name) {
                continue;
            }

            element.value = record[element.name] ?? "";
            element.disabled = !isDraft;
        }

        document.querySelector(
            "#catalog-save-button"
        ).hidden = !isDraft;

        const previousReview = document.querySelector("#catalog-previous-review");
        previousReview.textContent = record.review_notes
            ? `Previous review notes: ${record.review_notes}`
            : "";
        previousReview.hidden = !record.review_notes;
        reviewNotes.value = "";
        document.querySelector("#catalog-concept-approval").hidden = !(
            record.status === "in_review" && record.concept_status !== "approved"
        );

        for (const button of root.querySelectorAll(
            "[data-catalog-action]"
        )) {
            const action = button.dataset.catalogAction;

            const allowed = (
                action === "submit"
                    && record.status === "draft"
            ) || (
                action === "approve" && record.status === "in_review"
                    && record.concept_status === "approved"
            ) || (
                action === "reject" && record.status === "in_review"
            ) || (
                action === "retire"
                    && record.status !== "retired"
            );

            button.hidden = !allowed;
        }

        dialogFeedback.textContent = "";
    }

    // ==========================================
    // OPEN RECORD
    // ==========================================

    for (const button of root.querySelectorAll(
        "[data-open-record]"
    )) {
        button.addEventListener("click", () => {
            perform(async () => {
                const conceptId = button.dataset.openRecord;

                const record = await request(
                    `${api}/${encodeURIComponent(conceptId)}`
                );

                renderRecord(record);

                dialog.showModal();
            });
        });
    }

    // ==========================================
    // UPDATE DRAFT
    // ==========================================

    editForm.addEventListener("submit", (event) => {
        event.preventDefault();

        perform(async () => {
            if (!currentRecord) {
                return;
            }

            const payload = getPayload(editForm);

            payload.version = currentRecord.version;

            await request(
                `${api}/${currentRecord.concept_id}`,
                "PUT",
                payload
            );

            window.location.reload();
        });
    });

    // ==========================================
    // LIFECYCLE ACTIONS
    // ==========================================

    for (const button of root.querySelectorAll(
        "[data-catalog-action]"
    )) {
        button.addEventListener("click", () => {
            perform(async () => {
                if (!currentRecord) {
                    return;
                }

                const action = button.dataset.catalogAction;

                const notes = reviewNotes.value.trim();

                if (
                    ["approve", "reject"].includes(action)
                    && !notes
                ) {
                    throw new Error(
                        "Doctor review notes are required."
                    );
                }

                if (
                    action === "retire"
                    && !window.confirm(
                        "Retire this catalog record?"
                    )
                ) {
                    return;
                }

                await request(
                    `${api}/${currentRecord.concept_id}/${action}`,
                    "POST",
                    {
                        version: currentRecord.version,
                        notes: notes || null,
                    }
                );

                window.location.reload();
            });
        });
    }

    document.querySelector(
        "#catalog-close-dialog"
    ).addEventListener("click", () => {
        dialog.close();
    });

    root.querySelectorAll("[data-catalog-js]").forEach((element) => {
        element.disabled = false;
    });
});
