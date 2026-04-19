// 调试版本 - 最简单的方式
console.log("=== App.js loading ===");

document.addEventListener('DOMContentLoaded', function() {
    console.log("=== DOM Ready ===");
    
    // 使用setTimeout确保元素存在
    setTimeout(function() {
        var editBtn = document.getElementById('contextEditSource');
        var viewBtn = document.getElementById('contextViewSource');
        
        console.log("Edit button:", editBtn);
        console.log("View button:", viewBtn);
        
        if (editBtn) {
            editBtn.onclick = function() {
                alert("Edit clicked!");
                console.log("Edit button clicked!");
            };
            console.log("Edit onclick set");
        }
        
        if (viewBtn) {
            viewBtn.onclick = function() {
                alert("View clicked!");
                console.log("View button clicked!");
            };
            console.log("View onclick set");
        }
    }, 100);
});