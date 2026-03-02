// report.js - HTML报告交互功能

document.addEventListener('DOMContentLoaded', function() {
    console.log('HTML报告已加载');

    // 初始化报告功能
    initializeReport();

    // 添加交互功能
    addInteractivity();

    // 添加打印功能
    addPrintSupport();
});

/**
 * 初始化报告
 */
function initializeReport() {
    // 添加加载动画
    const sections = document.querySelectorAll('.info-section, .threat-section');
    sections.forEach((section, index) => {
        section.style.opacity = '0';
        section.style.transform = 'translateY(20px)';

        setTimeout(() => {
            section.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
            section.style.opacity = '1';
            section.style.transform = 'translateY(0)';
        }, index * 200);
    });

    // 更新时间戳
    updateTimestamp();

    // 检查风险等级并添加相应样式
    updateRiskDisplay();
}

/**
 * 添加交互功能
 */
function addInteractivity() {
    // 为信息项添加点击复制功能
    const infoItems = document.querySelectorAll('.info-item');
    infoItems.forEach(item => {
        item.addEventListener('click', function() {
            const value = this.querySelector('span').textContent;
            copyToClipboard(value);
            showToast('已复制到剪贴板: ' + value);
        });

        // 添加提示
        item.title = '点击复制内容';
        item.style.cursor = 'pointer';
    });

    // 添加展开/收起功能
    addExpandableContent();

    // 添加搜索功能
    addSearchFunctionality();
}

/**
 * 复制到剪贴板
 */
function copyToClipboard(text) {
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text);
    } else {
        // 降级方案
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        try {
            document.execCommand('copy');
        } catch (err) {
            console.error('复制失败:', err);
        }

        document.body.removeChild(textArea);
    }
}

/**
 * 显示提示消息
 */
function showToast(message) {
    // 创建提示元素
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #28a745;
        color: white;
        padding: 12px 20px;
        border-radius: 6px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 1000;
        font-size: 14px;
        font-weight: 500;
        opacity: 0;
        transform: translateX(100%);
        transition: all 0.3s ease;
    `;

    document.body.appendChild(toast);

    // 显示动画
    setTimeout(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translateX(0)';
    }, 100);

    // 自动隐藏
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => {
            document.body.removeChild(toast);
        }, 300);
    }, 3000);
}

/**
 * 添加展开/收起功能
 */
function addExpandableContent() {
    const sections = document.querySelectorAll('.info-section, .threat-section');

    sections.forEach(section => {
        const header = section.querySelector('h2');
        if (header) {
            // 添加展开/收起按钮
            const toggleBtn = document.createElement('button');
            toggleBtn.innerHTML = '−';
            toggleBtn.className = 'toggle-btn';
            toggleBtn.style.cssText = `
                background: none;
                border: none;
                font-size: 1.5rem;
                font-weight: bold;
                color: #3498db;
                cursor: pointer;
                margin-left: auto;
                padding: 0;
                width: 30px;
                height: 30px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.3s ease;
            `;

            header.style.display = 'flex';
            header.style.alignItems = 'center';
            header.appendChild(toggleBtn);

            // 点击事件
            toggleBtn.addEventListener('click', function() {
                const content = section.querySelector('.info-grid, p');
                if (content) {
                    const isCollapsed = content.style.display === 'none';

                    if (isCollapsed) {
                        content.style.display = '';
                        toggleBtn.innerHTML = '−';
                        toggleBtn.style.transform = 'rotate(0deg)';
                    } else {
                        content.style.display = 'none';
                        toggleBtn.innerHTML = '+';
                        toggleBtn.style.transform = 'rotate(180deg)';
                    }
                }
            });

            // 悬停效果
            toggleBtn.addEventListener('mouseenter', function() {
                this.style.backgroundColor = '#3498db';
                this.style.color = 'white';
            });

            toggleBtn.addEventListener('mouseleave', function() {
                this.style.backgroundColor = 'transparent';
                this.style.color = '#3498db';
            });
        }
    });
}

/**
 * 添加搜索功能
 */
function addSearchFunctionality() {
    // 创建搜索框
    const searchContainer = document.createElement('div');
    searchContainer.style.cssText = `
        position: fixed;
        top: 20px;
        left: 20px;
        z-index: 1000;
    `;

    const searchInput = document.createElement('input');
    searchInput.type = 'text';
    searchInput.placeholder = '搜索报告内容...';
    searchInput.style.cssText = `
        padding: 10px 15px;
        border: 2px solid #ddd;
        border-radius: 25px;
        font-size: 14px;
        width: 250px;
        outline: none;
        transition: all 0.3s ease;
        background: white;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    `;

    searchContainer.appendChild(searchInput);
    document.body.appendChild(searchContainer);

    // 搜索功能
    let searchTimeout;
    searchInput.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            const query = this.value.toLowerCase().trim();
            highlightSearchResults(query);
        }, 300);
    });

    // 焦点样式
    searchInput.addEventListener('focus', function() {
        this.style.borderColor = '#3498db';
        this.style.boxShadow = '0 2px 15px rgba(52, 152, 219, 0.3)';
    });

    searchInput.addEventListener('blur', function() {
        this.style.borderColor = '#ddd';
        this.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';
    });
}

/**
 * 高亮搜索结果
 */
function highlightSearchResults(query) {
    // 清除之前的高亮
    const highlighted = document.querySelectorAll('.search-highlight');
    highlighted.forEach(el => {
        const parent = el.parentNode;
        parent.replaceChild(document.createTextNode(el.textContent), el);
        parent.normalize();
    });

    if (!query) return;

    // 搜索并高亮
    const walker = document.createTreeWalker(
        document.querySelector('.report-content'),
        NodeFilter.SHOW_TEXT,
        null,
        false
    );

    const textNodes = [];
    let node;
    while (node = walker.nextNode()) {
        if (node.textContent.toLowerCase().includes(query)) {
            textNodes.push(node);
        }
    }

    textNodes.forEach(textNode => {
        const text = textNode.textContent;
        const regex = new RegExp(`(${query})`, 'gi');
        const highlightedText = text.replace(regex, '<span class="search-highlight" style="background: yellow; padding: 2px 4px; border-radius: 3px;">$1</span>');

        if (highlightedText !== text) {
            const wrapper = document.createElement('div');
            wrapper.innerHTML = highlightedText;
            textNode.parentNode.replaceChild(wrapper.firstChild || wrapper, textNode);
        }
    });
}

/**
 * 更新时间戳
 */
function updateTimestamp() {
    const now = new Date();
    const timestamp = now.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    // 如果页面有时间戳元素，更新它
    const timestampEl = document.querySelector('.timestamp');
    if (timestampEl) {
        timestampEl.textContent = `生成时间: ${timestamp}`;
    }
}

/**
 * 更新风险显示
 */
function updateRiskDisplay() {
    const riskBadge = document.querySelector('.risk-badge');
    if (riskBadge) {
        const riskLevel = riskBadge.textContent.toLowerCase();

        // 根据风险等级添加不同的动画效果
        if (riskLevel.includes('high')) {
            riskBadge.style.animation = 'pulse 1.5s infinite, shake 0.5s ease-in-out 3';
        } else if (riskLevel.includes('medium')) {
            riskBadge.style.animation = 'pulse 2s infinite';
        } else {
            riskBadge.style.animation = 'pulse 3s infinite';
        }
    }
}

/**
 * 添加打印支持
 */
function addPrintSupport() {
    // 创建打印按钮
    const printBtn = document.createElement('button');
    printBtn.innerHTML = '🖨️ 打印报告';
    printBtn.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #3498db;
        color: white;
        border: none;
        padding: 12px 20px;
        border-radius: 25px;
        font-size: 14px;
        font-weight: 500;
        cursor: pointer;
        box-shadow: 0 4px 15px rgba(52, 152, 219, 0.3);
        transition: all 0.3s ease;
        z-index: 1000;
    `;

    printBtn.addEventListener('click', function() {
        window.print();
    });

    printBtn.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-2px)';
        this.style.boxShadow = '0 6px 20px rgba(52, 152, 219, 0.4)';
    });

    printBtn.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
        this.style.boxShadow = '0 4px 15px rgba(52, 152, 219, 0.3)';
    });

    document.body.appendChild(printBtn);
}

/**
 * 打开截图模态框
 */
function openScreenshotModal(imgElement) {
    // 创建模态框
    const modal = document.createElement('div');
    modal.className = 'screenshot-modal';
    modal.innerHTML = `
        <span class="screenshot-modal-close">&times;</span>
        <div class="screenshot-modal-content">
            <img src="${imgElement.src}" alt="${imgElement.alt}">
        </div>
    `;

    document.body.appendChild(modal);
    modal.style.display = 'block';

    // 添加关闭事件
    const closeBtn = modal.querySelector('.screenshot-modal-close');
    closeBtn.addEventListener('click', function() {
        document.body.removeChild(modal);
    });

    // 点击背景关闭
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            document.body.removeChild(modal);
        }
    });

    // ESC键关闭
    const escHandler = function(e) {
        if (e.key === 'Escape') {
            document.body.removeChild(modal);
            document.removeEventListener('keydown', escHandler);
        }
    };
    document.addEventListener('keydown', escHandler);
}

// 添加震动动画
const style = document.createElement('style');
style.textContent = `
    @keyframes shake {
        0%, 100% { transform: translateX(0); }
        25% { transform: translateX(-2px); }
        75% { transform: translateX(2px); }
    }
`;
document.head.appendChild(style);