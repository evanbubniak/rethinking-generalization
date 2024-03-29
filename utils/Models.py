import tensorflow.keras as keras
import os

RATE_DECAY_FACTOR_PER_EPOCH = 0.95
MOMENTUM_PARAMETER = 0.9

everything_in_dir = os.listdir(os.getcwd())
folders_in_dir = filter(
    lambda f: os.path.isdir(f) and "output" in f,
    everything_in_dir)
max_folder_num = 0
for folder in folders_in_dir:
    folder_num = folder[(folder.find("_") + 1):]
    max_folder_num = max(int(folder_num), max_folder_num)
OUTPUT_DIR = "output_{}".format(max_folder_num + 1)
if not os.path.exists(OUTPUT_DIR):
    os.mkdir(OUTPUT_DIR)

if keras.backend.image_data_format() == 'channels_first':
    CHANNEL_AXIS = 1
else:
    CHANNEL_AXIS = 3

if keras.backend.image_data_format() == 'channels_first':
    BATCHNORM_AXIS = 1
else:
    BATCHNORM_AXIS = 3

class MidtermModel:
    def __init__(self, weight_decay = None):
        self.model_name = "model"
        self.model = keras.models.Model()
        self.initial_learning_rate = 0.1
        self.weight_decay = weight_decay

    def compile(self):

        sgd = keras.optimizers.SGD(
            learning_rate = self.initial_learning_rate,
            momentum = MOMENTUM_PARAMETER,
            nesterov = False
            )

        self.model.compile(
            loss="categorical_crossentropy",
            optimizer=sgd,
            metrics=["acc", "top_k_categorical_accuracy"])

        print("Finished compiling")
        self.model.summary()
    
    def fit(self, X_train, y_train, X_val, y_val,
        num_epoch, data_name, batch_size):
        run_name = "{}-{}".format(self.model_name, data_name)
        weights_file_name = "{}-weights.h5".format(run_name)
        weights_output_path = os.path.join(OUTPUT_DIR, weights_file_name) 
        log_file_name = "{}.csv".format(run_name)
        log_output_path = os.path.join(OUTPUT_DIR, log_file_name) 
        
        callbacks = [
                keras.callbacks.LearningRateScheduler(
                    self.learning_rate_schedule,
                    verbose = 0),
                keras.callbacks.ModelCheckpoint(weights_output_path,
                    monitor="acc",
                    save_best_only=True,
                    verbose=1),
                keras.callbacks.CSVLogger(
                    log_output_path)
                ]

        self.model_log = self.model.fit(X_train, y_train,
            batch_size = batch_size,
            epochs = num_epoch,
            verbose = 1,
            validation_data = (X_val, y_val),
            callbacks = callbacks)

        return self.model_log

    def evaluate(self, X_test, y_test):
        self.model.evaluate(X_test, y_test, verbose = 1)

    def learning_rate_schedule(self, epoch_num):
        return self.initial_learning_rate * \
            (RATE_DECAY_FACTOR_PER_EPOCH)**(epoch_num)

class MiniInceptionV3(MidtermModel):
    def __init__(self, input_shape, num_labels=10, use_batch_norm = True):
        super(MiniInceptionV3, self).__init__()
        self.initial_learning_rate = 0.1
        self.model_name = "MiniInceptionV3"
        if not use_batch_norm:
            self.model_name += "_without_BatchNorm"
        self.use_batch_norm = use_batch_norm
        input_layer = keras.layers.Input(shape = input_shape)
        x = self.conv_module(input_layer, 96,
            kernel_size = (3,3),
            strides = (1,1))
        x = self.inception_module(x, 32, 32)
        x = self.inception_module(x, 32, 48)
        x = self.downsample_module(x, 80)
        x = self.inception_module(x, 112, 48)
        x = self.inception_module(x, 96, 64)
        x = self.inception_module(x, 80, 80)
        x = self.inception_module(x, 48, 96)
        x = self.downsample_module(x, 96)
        x = self.inception_module(x, 176, 160)
        x = self.inception_module(x, 176, 160)
        x = keras.layers.GlobalAveragePooling2D(
            data_format = keras.backend.image_data_format())(x)
        x = keras.layers.Dense(
            num_labels, activation='softmax', name='predictions')(x)

        self.model = keras.models.Model(input_layer, x, name=self.model_name)

    def conv_module(self, input_layer, filters, kernel_size,
        padding='same', strides=(1, 1)):
        x = keras.layers.Conv2D(
            filters,
            kernel_size = kernel_size,
            strides=strides,
            padding=padding,
            use_bias=False)(input_layer)
        if self.use_batch_norm:
            x = keras.layers.BatchNormalization(
                axis=BATCHNORM_AXIS, scale=False)(x)
        x = keras.layers.Activation('relu')(x)
        return x

    def inception_module(self, input_layer, filters_1, filters_3):
        conv_module1 = self.conv_module(
            input_layer, filters = filters_1,
            kernel_size = (1, 1), strides = (1, 1))
        conv_module3 = self.conv_module(
            input_layer, filters = filters_3,
            kernel_size = (3, 3), strides = (1, 1))
        
        return keras.layers.concatenate(
            [conv_module1,
            conv_module3],
            axis = CHANNEL_AXIS)

    def downsample_module(self, input_layer, filters):
        max_pooling = keras.layers.MaxPooling2D(
            pool_size = (3,3), strides = (2,2),
            padding = 'same')(input_layer)
        conv_module3 = self.conv_module(
            input_layer, filters,
            kernel_size = (3, 3), strides = (2,2))

        return keras.layers.concatenate(
            [conv_module3,
            max_pooling],
            axis = CHANNEL_AXIS)

class LocalResponseNormalization(keras.layers.Layer):
    '''
    Code sample adapted from "Deep Learning with Keras" by Gulli and Pal
    '''
    def __init__(self, n=5, alpha=0.0005, beta=0.75, k=2, **kwargs):
        self.n = n
        self.alpha = alpha
        self.beta = beta
        self.k = k
        super(LocalResponseNormalization, self).__init__(**kwargs)

    def build(self, input_shape):
        self.shape = input_shape
        super(LocalResponseNormalization, self).build(input_shape)
    
    def call(self, x, mask=None):
        if keras.backend.image_data_format() == 'channels_first':
            _, f, r, c = self.shape
        else:
            _, r, c, f = self.shape
        squared = keras.backend.square(x)
        pooled = keras.backend.pool2d(squared,
            (self.n,self.n), strides = (1,1),
            padding = "same", pool_mode = "avg")
        summed = keras.backend.sum(pooled, axis=CHANNEL_AXIS, keepdims = True)
        averaged = self.alpha * keras.backend.repeat_elements(
            summed, f, axis=CHANNEL_AXIS)
        denom = keras.backend.pow(self.k + averaged, self.beta)
        return x / denom

    def get_output_shape_for(self, input_shape):
        return input_shape


class AlexNet(MidtermModel):
    def __init__(self, input_shape, num_labels=10):
        super(AlexNet, self).__init__()
        self.initial_learning_rate = 0.01
        self.model_name = "AlexNet"
        input_layer = keras.layers.Input(shape = input_shape)
        x = self.small_module(input_layer, filters = 96)
        x = self.small_module(x, filters = 256)
        x = keras.layers.Flatten()(x)
        x = keras.layers.Dense(384, activation = 'relu')(x)
        x = keras.layers.Dense(192, activation = 'relu')(x)
        x = keras.layers.Dense(
            num_labels,
            activation='softmax',
            name='predictions')(x)

        self.model = keras.models.Model(input_layer, x, name=self.model_name)

    def small_module(self, input_layer, filters = 96):
        x = keras.layers.Conv2D(
            filters,
            kernel_size = (5, 5),
            padding = 'valid')(input_layer)
        x = keras.layers.MaxPooling2D(
            pool_size = (3, 3), padding = "valid")(x)
        x = LocalResponseNormalization()(x)
        return x

class MLP(MidtermModel):
    def __init__(self, input_shape, num_labels=10,
                num_hidden_layers = 1,
                num_hidden_units = 512):
        super(MLP, self).__init__()
        self.model_name = "MLP_{}x{}".format(
            num_hidden_layers, num_hidden_units)
        input_layer = keras.layers.Input(shape = input_shape)
        x = keras.layers.Flatten()(input_layer)
        for hidden_layer in range(num_hidden_layers):
            x = keras.layers.Dense(num_hidden_units)(x)
            x = keras.layers.Activation("relu")(x)
        x = keras.layers.Dense(
            num_labels,
            activation = "softmax",
            name = "predictions")(x)
        self.model = keras.models.Model(
            input_layer, x, name=self.model_name)
    