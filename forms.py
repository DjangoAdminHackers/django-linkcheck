from django import forms

class FindForm(forms.Form):
    find = forms.CharField()
    
class ReplaceForm(forms.Form):
    replace = forms.CharField()