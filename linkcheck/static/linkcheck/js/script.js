function showProgressDots(numberOfDots) {
    var progress = document.getElementById('progressDots');
    if (!progress) return;
    switch(numberOfDots) {
        case 1:
            progress.innerHTML = '.&nbsp;&nbsp;';
            timerHandle = setTimeout('showProgressDots(2)',200);
            break;
        case 2:
            progress.innerHTML = '..&nbsp;';
            timerHandle = setTimeout('showProgressDots(3)',200);
            break;
        case 3:
            progress.innerHTML = '...';
            timerHandle = setTimeout('showProgressDots(1)',200);
            break;
    }
}

$(document).ready(function() {

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    $(".ignore").submit(function(){
        $.post(this.action, {'csrfmiddlewaretoken': csrfToken}, (data) => {
            $('tr#link' + data.link).hide('medium');
            var ignored_count = parseInt($('#ignored_count').text());
            ignored_count++;
            $('#ignored_count').text(ignored_count);
        });
        return false;
    });

    $(".unignore").submit(function(){
        $.post(this.action, {'csrfmiddlewaretoken': csrfToken}, (data) => {
            $('tr#link' + data.link).hide('medium');
            var ignored_count = parseInt($('#ignored_count').text());
            ignored_count--;
            $('#ignored_count').text(ignored_count);
        });
        return false;
    });

    $(".recheck").submit(function(){
        $(this).closest('tr').find('td.link_message').html('Checking<span id="progressDots"></span>');
        showProgressDots(1);
        $.post(this.action, {'csrfmiddlewaretoken': csrfToken}, (data) => {
            var links = data['links'];
            for (var link in links) {
                $('tr#link'+links[link]).find('td.link_message').text(data['message']).css('color', data['colour']);
            }
        });
        return false;
    });
});
