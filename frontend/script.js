document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const fileList = document.getElementById('file-list');
    const downloadAllContainer = document.getElementById('download-all-container');
    const downloadAllBtn = document.getElementById('download-all-btn');

    const successfulConversions = [];

    // ── Show/hide Download All button ──
    function updateDownloadAllVisibility() {
        downloadAllContainer.style.display = successfulConversions.length > 0 ? 'block' : 'none';
    }

    // ── Download All handler ──
    downloadAllBtn.addEventListener('click', () => {
        if (successfulConversions.length === 0) return;

        const originalHtml = downloadAllBtn.innerHTML;
        downloadAllBtn.innerHTML = '<div class="spinner" style="width:18px;height:18px;border-width:2px"></div><span>Creating ZIP...</span>';
        downloadAllBtn.classList.add('loading');
        downloadAllBtn.disabled = true;

        fetch('/api/download-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ files: successfulConversions })
        })
        .then(res => {
            if (!res.ok) throw new Error('ZIP creation failed');
            return res.blob();
        })
        .then(blob => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'converted_presentations.zip';
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        })
        .catch(err => {
            console.error(err);
            alert('Failed to download ZIP file.');
        })
        .finally(() => {
            downloadAllBtn.innerHTML = originalHtml;
            downloadAllBtn.classList.remove('loading');
            downloadAllBtn.disabled = false;
        });
    });

    // ── Drag & drop events ──
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(evt => {
        dropZone.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }, false);
        document.body.addEventListener(evt, e => { e.preventDefault(); e.stopPropagation(); }, false);
    });

    ['dragenter', 'dragover'].forEach(evt => {
        dropZone.addEventListener(evt, () => dropZone.classList.add('dragover'), false);
    });
    ['dragleave', 'drop'].forEach(evt => {
        dropZone.addEventListener(evt, () => dropZone.classList.remove('dragover'), false);
    });

    dropZone.addEventListener('drop', e => {
        handleFiles(e.dataTransfer.files);
    });

    dropZone.addEventListener('click', e => {
        if (e.target !== fileInput && !e.target.classList.contains('browse-btn')) {
            fileInput.click();
        }
    });

    fileInput.addEventListener('change', function () {
        handleFiles(this.files);
        this.value = ''; // allow re-selecting the same file
    });

    function handleFiles(files) {
        [...files].forEach(uploadFile);
    }

    // ── Upload + convert a single file ──
    function uploadFile(file) {
        const ext = file.name.split('.').pop().toLowerCase();
        if (ext !== 'ppt' && ext !== 'pptx') {
            alert(`"${file.name}" is not supported. Only .ppt and .pptx files are allowed.`);
            return;
        }

        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <div class="file-info">
                <div class="file-icon">📊</div>
                <div class="file-details">
                    <span class="file-name" title="${file.name}">${file.name}</span>
                    <span class="file-status">Uploading & Converting…</span>
                </div>
            </div>
            <div class="file-actions">
                <div class="spinner"></div>
            </div>
        `;

        // Newest files at top
        fileList.firstChild
            ? fileList.insertBefore(fileItem, fileList.firstChild)
            : fileList.appendChild(fileItem);

        const statusEl  = fileItem.querySelector('.file-status');
        const actionsEl = fileItem.querySelector('.file-actions');

        const formData = new FormData();
        formData.append('file', file);

        fetch('/api/convert', { method: 'POST', body: formData })
            .then(res => {
                if (!res.ok) return res.json().then(e => { throw new Error(e.detail || 'Conversion failed'); });
                return res.json();
            })
            .then(data => {
                statusEl.textContent = 'Conversion Complete';
                statusEl.style.color = 'var(--success)';
                actionsEl.innerHTML = `<a href="${data.download_url}" class="download-link" download="${data.pdf_filename}">Download PDF</a>`;

                // Track for Download All
                const parts = data.download_url.split('/api/download/');
                if (parts.length > 1) {
                    successfulConversions.push({
                        filename: parts[1].split('?')[0],
                        original_name: data.pdf_filename
                    });
                    updateDownloadAllVisibility();
                }
            })
            .catch(err => {
                statusEl.textContent = 'Error';
                statusEl.style.color = 'var(--error)';
                actionsEl.innerHTML = `<span class="error-text" title="${err.message}">Conversion failed</span>`;
                console.error(err);
            });
    }
});
