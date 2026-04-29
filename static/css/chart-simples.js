/* Chartist.js - Versão Ultraleve para Gráficos */
(function (root, factory) {
  if (typeof define === 'function' && define.amd) { define([], factory); } 
  else if (typeof exports === 'object') { module.exports = factory(); } 
  else { root.Chartist = factory(); }
}(this, function () {
  var Chartist = { version: '0.11.4' };
  Chartist.Pie = function (query, data) {
    var container = document.querySelector(query);
    if (!container) return;
    var html = '<svg viewBox="0 0 100 100" style="transform: rotate(-90deg); border-radius: 50%; width: 100%;">';
    var total = data.series.reduce(function(a, b) { return a + b; }, 0);
    var accum = 0;
    var colors = ['#2B2D42', '#8D99AE', '#EDF2F4', '#EF233C', '#D90429'];
    
    data.series.forEach(function(val, i) {
        var start = (accum / total) * 100;
        var end = ((accum + val) / total) * 100;
        var dash = (val / total) * 100;
        html += '<circle cx="50" cy="50" r="25" fill="none" stroke="' + colors[i % colors.length] + 
                '" stroke-width="50" stroke-dasharray="' + dash + ' 100" stroke-dashoffset="-' + start + '" />';
        accum += val;
    });
    html += '</svg>';
    
    var legend = '<div style="margin-top:20px; font-size: 14px; text-align: left;">';
    data.labels.forEach(function(lab, i) {
        legend += '<div><span style="display:inline-block; width:12px; height:12px; background:' + colors[i % colors.length] + '; margin-right:8px;"></span>' + lab + ': R$ ' + data.series[i] + '</div>';
    });
    legend += '</div>';
    
    container.innerHTML = html + legend;
  };
  return Chartist;
}));
