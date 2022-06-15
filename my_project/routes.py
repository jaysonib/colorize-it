import os
import secrets
from PIL import Image
from flask import render_template, url_for, flash, redirect, request, abort, send_file
from my_project import app, db, bcrypt
from my_project.forms import RegistrationForm, LoginForm, UpdateAccountForm, PostForm, UpdatePostForm
from my_project.models import User, Post
from flask_login import login_user, current_user, logout_user, login_required

@app.route("/")
@app.route("/home")
def home():
	page = request.args.get('page', 1, type=int)
	posts = Post.query.filter_by(visibility=0).order_by(Post.date_posted.desc()).paginate(page=page, per_page=2)
	return render_template('home.html', post=posts)


@app.route("/about")
def about():
	return render_template('about.html', title='About')

@app.route("/register", methods=['GET', 'POST'])
def register():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	form = RegistrationForm()
	if form.validate_on_submit():
		hashed_password = bcrypt.generate_password_hash(form.password.data).decode('UTF-8')
		user = User(username=form.username.data, email=form.email.data, password=hashed_password)
		db.session.add(user)
		db.session.commit()
		flash('Your Account has been created! You are now able to Log In','success')
		return redirect(url_for('login'))
	return render_template('register.html', title='register', form= form)


@app.route("/login", methods=['GET', 'POST'])
def login():
	if current_user.is_authenticated:
		return redirect(url_for('home'))
	form = LoginForm()
	if form.validate_on_submit():
		user = User.query.filter_by(email=form.email.data).first()
		if user and bcrypt.check_password_hash(user.password, form.password.data):
			login_user(user, remember=form.remember.data)
			next_page = request.args.get('next')
			return redirect(next_page) if next_page else redirect(url_for('home'))
		else:
			flash('Login Unsuccessful. Please check Email and Password','danger')
	return render_template('login.html', title='login', form= form)


@app.route("/logout")
def logout():
	logout_user()
	return redirect(url_for('home'))



def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)
    
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_fn


import numpy as np
import argparse
import cv2






@app.route("/account", methods=['GET', 'POST'])
@login_required
def account():
    form = UpdateAccountForm()
    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('Your account has been updated!', 'success')
        return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file)
    return render_template('account.html', title='Account',
                           image_file=image_file, form=form)


def convert(path):
	args = path


	# load our serialized black and white colorizer model and cluster
	# center points from disk
	print("[INFO] loading model...")
	prototxt_file = os.path.join(app.root_path, 'model/colorization_deploy_v2.prototxt')
	caffe_file = os.path.join(app.root_path, 'model/colorization_release_v2.caffemodel')
	null_file = os.path.join(app.root_path, 'model/pts_in_hull.npy')
	net = cv2.dnn.readNetFromCaffe(prototxt_file,caffe_file)
	pts = np.load(null_file)

	# add the cluster centers as 1x1 convolutions to the model
	class8 = net.getLayerId("class8_ab")
	conv8 = net.getLayerId("conv8_313_rh")
	pts = pts.transpose().reshape(2, 313, 1, 1)
	net.getLayer(class8).blobs = [pts.astype("float32")]
	net.getLayer(conv8).blobs = [np.full([1, 313], 2.606, dtype="float32")]

	# load the input image from disk, scale the pixel intensities to the
	# range [0, 1], and then convert the image from the BGR to Lab color
	# space
	print("args = ",args)
	image = cv2.imread(args)

	scaled = image.astype("float32") / 255.0
	lab = cv2.cvtColor(scaled, cv2.COLOR_BGR2LAB)

	# resize the Lab image to 224x224 (the dimensions the colorization
	# network accepts), split channels, extract the 'L' channel, and then
	# perform mean centering
	resized = cv2.resize(lab, (224, 224))
	L = cv2.split(resized)[0]
	L -= 50

	# pass the L channel through the network which will *predict* the 'a'
	# and 'b' channel values
	'print("[INFO] colorizing image...")'
	net.setInput(cv2.dnn.blobFromImage(L))
	ab = net.forward()[0, :, :, :].transpose((1, 2, 0))

	# resize the predicted 'ab' volume to the same dimensions as our
	# input image
	ab = cv2.resize(ab, (image.shape[1], image.shape[0]))

	# grab the 'L' channel from the *original* input image (not the
	# resized one) and concatenate the original 'L' channel with the
	# predicted 'ab' channels
	L = cv2.split(lab)[0]
	colorized = np.concatenate((L[:, :, np.newaxis], ab), axis=2)

	# convert the output image from the Lab color space to RGB, then
	# clip any values that fall outside the range [0, 1]
	colorized = cv2.cvtColor(colorized, cv2.COLOR_LAB2BGR)
	colorized = np.clip(colorized, 0, 1)

	# the current colorized image is represented as a floating point
	# data type in the range [0, 1] -- let's convert to an unsigned
	# 8-bit integer representation in the range [0, 255]
	colorized = (255 * colorized).astype("uint8")

	# show the original and output colorized images
	cv2.imshow("Original", image)
	cv2.imshow("Colorized", colorized)
	img_name = args.split('/')
	print("img_name = ",img_name)
	image_name = img_name[1].split('\\')
	print("image_name = ",image_name)
	outpath = os.path.join(app.root_path,'static/output_pics',image_name[1])
	#save the image
	cv2.imwrite(outpath, colorized)
	return image_name[1]



def save_input_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/input_pics', picture_fn)
    form_picture.save(picture_path)

    output_fn = convert(picture_path)
    picture_fn_2 = [output_fn, picture_fn]

    return picture_fn_2


@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
	form = PostForm()
	if form.validate_on_submit():
		list_picture_file = save_input_picture(form.input_picture.data)
		
		output_picture_file = list_picture_file[0]
		input_picture_file = list_picture_file[1]
		print("input_picture_file = ",input_picture_file)
		print("input_picture_file = ",output_picture_file)
		visible = request.form.get('comp_select')
		post = Post(title=form.title.data, content= form.content.data, visibility=visible, image_file=input_picture_file, output_file=output_picture_file, author=current_user)
		db.session.add(post)
		db.session.commit()
		flash('Your post has been created!','success')
		return redirect(url_for('user_post',username=current_user.username))
	return render_template('create_post.html', title='New Post', form=form, legend='Convert Image', visibility=0)



@app.route("/post/<int:post_id>")
def post(post_id):
	post = Post.query.get_or_404(post_id)
	return render_template('post.html', title=post.title, post=post)


@app.route("/post/<int:post_id>/update", methods=['GET', 'POST'])
@login_required
def update_post(post_id):
	post = Post.query.get_or_404(post_id)
	if post.author != current_user:
		abort(403)


	form = UpdatePostForm()

	image_file_1 = url_for("static", filename="input_pics/" + post.image_file)
	image_file_2 = url_for("static", filename="output_pics/" + post.output_file)
	visible = request.form.get('comp_select')
	if form.validate_on_submit():
		post.title = form.title.data
		post.content = form.content.data
		post.visibility = visible
		db.session.commit()
		flash('Your post has been updated!','success')
		return redirect(url_for('post',post_id=post.id))
	elif request.method == 'GET':
		form.title.data = post.title
		form.content.data = post.content
		form.input_picture = image_file_1
	previous_visible = post.visibility
	return render_template('create_post.html', title='Update Post', form=form, legend='Update Content', image_file_1=image_file_1, image_file_2=image_file_2, visible=previous_visible)


@app.route("/post/<int:post_id>/delete", methods=['POST'])
@login_required
def delete_post(post_id):
	post = Post.query.get_or_404(post_id)
	if post.author != current_user:
		abort(403)
	db.session.delete(post)
	db.session.commit()
	flash("Your post has been deleted!","success")
	return redirect(url_for('home'))



@app.route("/user/<string:username>")
def user_post(username):
	page = request.args.get('page', 1, type=int)
	user = User.query.filter_by(username=username).first_or_404()
	if current_user.is_authenticated:
		posts = Post.query.filter_by(author=user)\
			.order_by(Post.date_posted.desc())\
			.paginate(page=page, per_page=3)
	else:
		posts = Post.query.filter_by(author=user,visibility=0)\
			.order_by(Post.date_posted.desc())\
			.paginate(page=page, per_page=3)
	return render_template('user_post.html', post=posts, user=user)


@app.route("/abstract")
def abstract():
	return render_template('abstract.html', title='Abstract')

@app.route("/future_work")
def future_work():
	return render_template('future_work.html', title='Future Work')


@app.route("/created_by")
def created_by():
	return render_template('created_by.html', title='Created By')


@app.route('/download/<string:filename>')
def download_file(filename):
	path = os.path.join(app.root_path, 'static\\output_pics', filename)
	print(path)
	return send_file(path, as_attachment=True)
	